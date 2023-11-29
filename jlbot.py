#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sets percentage in loan sells.

This bot written to set percentage on a platform https://jetlend.ru/

Copyright 2023 Alic Znapy
SPDX-License-Identifier: Apache-2.0
"""

from sys import stdout as sys_stdout
from typing import List, Dict, Set, Union, cast, Optional
from json import (
    dump as json_dump,
    load as json_load
)
from datetime import datetime, timedelta
from time import sleep
from string import Template
from logging import (
    INFO as logging_INFO,
    WARNING as logging_WARNING,
    info,
    warning,
    basicConfig as logging_basicConfig,
    StreamHandler as logging_StreamHandler,
    handlers as logging_handlers
)
from pathlib import Path
from requests import request
from requests.structures import CaseInsensitiveDict

try:
    import tomllib  # type: ignore [import, unused-ignore]
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore [no-redef]

BASE_DIR = Path(__file__).resolve().parent

JetPath = Dict[str, str]  # See Engine.jet_path (keys from "_get_section()")
JetRequestField = Union[str, int, float]  # See Commands._requests_my
# See Commands.reduce_prices: loan_id, loan_request_id, count, min_price
Target = Dict[str, str]
ExistRequests = Dict[str, Dict[str, str]]
Cookie = Dict[str, Union[str, datetime]]


class Settings:  # pylint: disable=too-few-public-methods
    """Settings saved in pyproject.toml."""

    def _clean_cookies(self, cookies: Optional[List[Cookie]]
                       ) -> Dict[str, str]:
        result: Dict[str, str] = {}
        if cookies is None:
            return result

        for cookie in cookies:
            if cast(datetime, cookie["expires"]) < datetime.utcnow():
                raise ValueError(f"cookie \"{cookie['name']}\" expired")
            result[str(cookie["name"])] = str(cookie["value"])
        return result

    def __init__(self) -> None:
        with open(BASE_DIR / "pyproject.toml", "rb") as file:
            toml = tomllib.load(file)

        post_delta = toml["bot-settings"]["post_delta"]
        self.post_delta = timedelta(seconds=post_delta)
        self.request_timeout = toml["bot-settings"]["request_timeout"]
        self.step_reduce = toml["bot-settings"]["step_reduce"]

        self.headers = toml["bot-settings"].get("headers", {})
        cookies = toml["bot-settings"].get("cookies", None)
        self.cookies = self._clean_cookies(cookies)


class Engine:
    """Https requests to jetlend's API."""

    def __init__(self, settings: Settings):
        self._sessionid = Engine._get_input_cookie(settings.cookies,
                                                   "sessionid")
        self._csrftoken = Engine._get_input_cookie(settings.cookies,
                                                   "csrftoken")
        self.settings = settings
        self._prev_post = datetime.today() - settings.post_delta

    @staticmethod
    def _get_input_cookie(cookies: Dict[str, str], cookie_name: str) -> str:
        """Get sessionid or csrftoken."""
        val = cookies.get(cookie_name, None)
        if val is None:
            val = input(f"input {cookie_name}: ")
        if len(val) != 32:
            raise ValueError(f"the {cookie_name} must be 32 characters long")
        return val

    @staticmethod
    def _get_section(name: str) -> Dict[str, Union[str, Template]]:
        result: Dict[str, Union[str, Template]] = {
            "name": name,
            "referer": Template("https://jetlend.ru/invest/v3/market/"
                                "requests")}
        referer_market = Template("https://jetlend.ru/invest/v3/company/"
                                  "${loan_id}/market")
        count_min_price = Template('{"count":${count},'
                                   '"min_price":${min_price}}')
        if name == "requests_my":
            result["method"] = "GET"
            result["path"] = Template("exchange/requests/my")

        if name == "loan_overview":
            result["method"] = "GET"
            result["path"] = Template("exchange/loans/${loan_id}/overview")

        elif name == "loan_request_cancel":
            result["method"] = "POST"
            result["json"] = Template("{}")
            result["path"] = Template("exchange/requests/${loan_request_id}/"
                                      "cancel")
        elif name == "loan_sell_preview":
            result["referer"] = referer_market
            result["method"] = "POST"
            result["json"] = count_min_price
            result["path"] = Template("exchange/loans/${loan_id}/sell/preview")

        elif name == "loan_sell":
            result["referer"] = referer_market
            result["method"] = "POST"
            result["json"] = count_min_price
            result["path"] = Template("exchange/loans/${loan_id}/sell")

        if result.get("path", None) is None:
            raise ValueError(f"Unknown section {name}")

        # not used (all with GET):
        #   exchange/loans/{loan_id}/dom/summary
        #   exchange/loans/{loan_id}/dom/records
        #   requests/{loan_id}/info

        return result

    @staticmethod
    def jet_path(section_name: str,
                 params: Optional[Dict[str, str]] = None) -> JetPath:
        """Construct JetPath for use in requests later."""
        if params is None:
            params = {}
        result: JetPath = {}
        for key, val in Engine._get_section(section_name).items():
            if isinstance(val, str):
                result[key] = val
            elif isinstance(val, Template):
                result[key] = val.substitute(**params)
            else:
                raise ValueError("unknown value for jet_path")
        return result

    def _headers(self, jet_path: JetPath) -> Dict:
        """Headers for request to jetlend.ru."""
        result = {"Referer": jet_path["referer"]}
        result.update(self.settings.headers)

        if "Content-Type" not in result:
            result["Content-Type"] = "application/json;charset=utf-8"

        if jet_path["name"] in ["loan_request_cancel", "loan_sell_preview",
                                "loan_sell"]:
            result["Origin"] = "https://jetlend.ru"
            result["X-CSRFToken"] = self._csrftoken

        return result

    def _cookies(self) -> Dict:
        """Cookies for request to jetlend.ru."""
        result = {
            'csrftoken': self._csrftoken,
            'sessionid': self._sessionid
        }
        result.update(self.settings.cookies)
        return result

    def _params_for_request(self, jet_path: JetPath) -> Dict:
        """Create nested params for call requests."""
        result = {
            "headers": self._headers(jet_path),
            "cookies": self._cookies(),
            "method": jet_path["method"],
            "url": self._full_url(jet_path),
            "timeout": self.settings.request_timeout
        }
        if jet_path.get("json", None) is not None:
            result["data"] = jet_path["json"]  # str without whitespaces
        return result

    @staticmethod
    def _full_url(jet_path: JetPath) -> str:
        """Get full url."""
        return f"https://jetlend.ru/invest/api/{jet_path['path']}"

    def _post_delay(self, jet_path: JetPath) -> None:
        if jet_path["method"] != "POST":
            return
        if self._prev_post > datetime.today() - self.settings.post_delta:
            sleep(1)

    @staticmethod
    def _process_request_text(text: str, headers: CaseInsensitiveDict) -> str:
        """
        Reduce the text of request.

        If it is an html return the link to the created file
        """
        if "Content-Type" not in headers \
                or headers["Content-Type"] != "text/html; charset=UTF-8":
            return text
        file_name = BASE_DIR / "response.html"
        with open(file_name, "w", encoding="utf8") as file:
            file.write(text)
        return f"...(saved to {file_name})"

    def call(self, jet_path: JetPath) -> Dict:
        """Receive json from site."""
        self._post_delay(jet_path)
        params = self._params_for_request(jet_path)
        response = request(**params)
        if response.status_code != 200:
            text = self._process_request_text(response.text, response.headers)
            warning(f"exited with status_code {response.status_code}"
                    f" jet_path {jet_path} text {text},"
                    f" headers {response.headers}"
                    f" request.body {response.request.body!r}")
        response.raise_for_status()
        return cast(Dict, response.json())


class Commands:
    """Commands to manage jetlend."""

    TARGET_FILE_NAME = BASE_DIR / 'target_loan_prices.json'

    def __init__(self, engine: Engine):
        self._engine = engine

    def _send(self, section_name: str, params: Optional[Dict[str, str]] = None
              ) -> Dict:
        """Send request to Jetlend and recieve json."""
        if params is None:
            params = {}
        jet_path = self._engine.jet_path(section_name, params)
        unswer = self._engine.call(jet_path)

        info(f"{jet_path['path']}: {str(unswer)}")
        if unswer["status"] == "error":
            warning(unswer["error"])
        if unswer['status'] != 'OK':
            raise ValueError(f"recieved status {unswer['status']} "
                             f"in request {section_name} ({jet_path})")
        return unswer

    def _requests_my(self) -> List[Dict[str, JetRequestField]]:
        """Get my loans requests (sells only)."""
        result: List[Dict[str, JetRequestField]] = []

        response = self._send("requests_my")

        fields = ['loan_id', 'loan_name', 'interest_rate', 'id',
                  'amount', 'principal_debt', 'discount', 'ytm',
                  'contract_count', 'contract_price']
        for my_request in response['requests']:
            cleaned = dict(((k, v) for k, v in my_request.items()
                            if k in fields))

            if my_request['type'] != 'sell':
                cleaned['type'] = my_request['type']
                warning(f"Обнаружена заявка не на продажу {cleaned}")
                continue

            if my_request['is_owner'] != 1:
                cleaned['is_owner'] = my_request['is_owner']
                warning(f"Обнаружена не моя заявка на продажу {cleaned}")
                continue

            if my_request['status'] != 'active':
                cleaned['status'] = my_request['status']
                warning("Обнаружена заявка с неактивным статусом {cleaned}")
                continue

            result.append(cleaned)

        return result

    def _reduced_prices(self) -> List[Target]:
        """Get reduced prices from requests_my."""
        result: List[Target] = []
        step_reduce = self._engine.settings.step_reduce
        for my_request in self._requests_my():
            if not isinstance(my_request["contract_price"], float):
                raise ValueError("expected float in contract_price")
            new_price = my_request["contract_price"] - step_reduce
            result.append({
                "loan_id": str(my_request["loan_id"]),
                "loan_name": str(my_request["loan_name"]),
                "min_price": f"{new_price:.3}"})
        return result

    def get_target_loan_prices(self) -> List[Target]:
        """
        Get targets from file target_loan_prices.json.

        If the file doesn't exist - create it (current prices with reduce).
        """
        try:
            with open(self.TARGET_FILE_NAME, mode='r', encoding="utf-8") \
                    as file:
                return cast(List[Target], json_load(file))
        except FileNotFoundError:
            targets = self._reduced_prices()
            with open(self.TARGET_FILE_NAME, mode='w', encoding="utf-8") \
                    as file:
                json_dump(targets, file, indent=4, ensure_ascii=False)
            return targets

    def get_exist_requests(self) -> ExistRequests:
        """Get from JetLend current requests for the sale of loans."""
        result: ExistRequests = {}
        fields = ["id", "contract_price", "amount"]
        for my_request in self._requests_my():
            loan_id = str(my_request["loan_id"])
            contract_price_str = f"{my_request['contract_price']:.3}"
            result[loan_id] = dict(
                ((k, str(v)) for k, v in my_request.items() if k in fields))
            result[loan_id]["contract_price"] = contract_price_str
        return result

    @staticmethod
    def _tasks_for_target(target: Target,
                          exist_request: Optional[Dict[str, str]]
                          ) -> Set[str]:
        """Get list of things we need to do."""
        if exist_request is None:
            # nothing to cancel, go to sell
            return {"do_sell"}

        if exist_request['contract_price'] == target["min_price"]:
            # nothing to cancel, nothing to sell
            return set()

        return {"do_cancel", "do_sell"}

    @staticmethod
    def _checks_loan_overview(response: Dict, target: Target) -> None:
        loan = response["data"]["loan"]
        if loan['history_overdue_days'] != 0:
            warning("history_overdue_days"
                    f" {loan['history_overdue_days']} {target}")
        if loan['financial_discipline'] != 1.0:
            warning("financial_discipline"
                    f" {loan['financial_discipline']} {target}")
        if loan['restructured'] is True:
            warning(f"restructured {target}")
        if loan['overdue_days'] != 0:
            warning(f"overdue days {loan['overdue_days']} {target}")
        if loan['active_overdue'] is True:
            warning("active overdue {target}")

        personal = response["data"]["personal"]
        contracts_count = personal["contracts_count"]

        if "best_price" in response["data"]["sell"]:
            best_price = response["data"]["sell"]["best_price"]
            best_price_count = response["data"]["sell"]["best_price_count"]
            if best_price < float(target["min_price"]):
                warning(f"there is sells loan {target['loan_id']}"
                        f" with price {best_price}"
                        f" and numbers {best_price_count}"
                        f" (we try to sell {contracts_count}"
                        f" for {target['min_price']})")

    def _do_loan_overview(self, target: Target) -> int:
        """Get number for sale from loan_overview request."""
        response = self._send("loan_overview", {"loan_id": target["loan_id"]})

        self._checks_loan_overview(response, target)
        personal = response["data"]["personal"]
        contracts_count = int(personal["contracts_count"])

        # summary_interest_revenue = personal["summary_interest_revenue"]
        # if contracts_count == 0:
        #     warning(f"contract {target['loan_id']} already for sale"
        #             f" with price {summary_interest_revenue}")

        return contracts_count

    def change_loans_price(self, targets: List[Target],
                           exist_requests: ExistRequests) -> None:
        """Send to JetLend new prices."""
        for target in targets:

            exist_request = exist_requests.get(target["loan_id"], None)
            tasks = self._tasks_for_target(target, exist_request)

            if "do_cancel" in tasks:
                assert exist_request is not None  # checked in tasks
                params = {"loan_request_id": exist_request["id"]}
                self._send("loan_request_cancel", params)

            if ("do_sell" in tasks) and (
                    contracts_count := self._do_loan_overview(target)):

                params = {"loan_id": target["loan_id"],
                          "count": str(contracts_count),
                          "min_price": target["min_price"]}

                # check no error in answer (json)
                self._send("loan_sell_preview", params)
                self._send("loan_sell", params)
                # The result of "loan_overview" may be not updated yet
                self._send("loan_overview", {"loan_id": target["loan_id"]})


def loginit() -> None:
    """Initialize logging."""
    console = logging_StreamHandler(sys_stdout)
    logfile = logging_handlers.RotatingFileHandler(
        BASE_DIR / "main.log", maxBytes=2_000_000, backupCount=5)

    console.setLevel(logging_WARNING)
    logfile.setLevel(logging_INFO)

    logging_basicConfig(level=min(console.level, logfile.level),
                        handlers=[console, logfile],
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt='%Y%m%d_%H%M%S')


if __name__ == "__main__":
    loginit()

    commands = Commands(Engine(Settings()))

    target_loan_prices = commands.get_target_loan_prices()
    warning(f"number of targets: {len(target_loan_prices)}")

    current_exist_requests = commands.get_exist_requests()
    amount = sum(float(req["amount"])
                 for req in current_exist_requests.values())
    warning(f"number of exist requests: {len(current_exist_requests)}, "
            f"amount: {amount:.2f}")

    # If an exception occurs - the achieved target
    #   will be skipped at the next execute after verification
    commands.change_loans_price(target_loan_prices,
                                current_exist_requests)
