## Briefly about JLBot

The bot sets percentage of loan sells in the lending platform [jetlend.ru](https://jetlend.ru/).

(описание на русском [ниже](#more-details-in-russian))

Features:
- If there is no *target_loan_prices.json* file - bot checks the current loans sells on the site and writes the positions minus 1% (depends on variable *step_reduce*) to the file.
- Extracts prices from the file and sets them on the lending platform.

To use it, you must receive 2 cookies (**sessionid** and **csrftoken**) from your browser:
- In firefox press *Ctrl+Shift+E* and look it up on the **Storage** tab.
- In Chrome by right-click and look it up on the **Inspect > Application tab > Storage > Cookies**

You can add this cookies to pyproject.toml in **\[bot-settings\]** section or input every start in console.

## More details in Russian

Бот предназначен для периодического понижения цен выставленных на продажу займов на платформе [jetlend.ru](https://jetlend.ru).

Платформа предоставляет возможность выставить займы на продажу, но изменять цену для большого количества заявок - слишком времязатратная задача. Бот помог мне распродать займы и я решил поделиться кодом - вдруг кому понадобится.

Используемое API платформой не документировано в открытом доступе и в подписываемом соглашении при регистрации я не нашел пункта об его использовании, поэтому подход используется на свой страх и риск.

Возможности:
- Считывает с платформы текущие выставленные займы и сохраняет пониженную на 1% (зависит от значения настройки *step_reduce*) цену в файл *target_loan_prices.json*.
- Устанавливает целевые цены на платформе по количество в займе. По мере установки оповещает о наличии индикаторов проблем с займами (рейтинг заемщика, просрочка).

Платформа периодически снимает заявки на продажу (ограничения на продажу займов, если должних просрочил какие-то платежи этого или другого займа), поэтому их нужно выставлять снова вручную.

Файл *target_loan_prices.json* можно менять самостоятельно перед запуском. Для установки по займу *12345* своей цены *99,9%* можно вручную создать файл со строкой *\["loan_id": "12345", "min_price": "0.999"\]*.  Для очередного понижения цен на шаг - просто удалить файл и запустить скрипт - файл создастся автоматически и по нему сразу же изменятся цены.

Для использования необходимо в вашем браузере с сайта взять минимум 2 переменные (cookies): **sessionid** и **csrftoken** (лучше сохранить все, перечисленные в файле настроек). Инструкция для англоязычного интерфейса:
- В firefox нажать *Ctrl+Shift+E* и найти их на вкладке **Storage**.
- В Chrome по правому клику зайти в **Inspect > Application tab > Storage > Cookies** и найти эти переменные.

Две переменные можно сохранить в файл настроек *pyproject.toml* в раздел **[bot-settings]** (по примеру уже добавленной одной переменной) или вводить в консоль при каждом запуске бота. При необходимости, в файле настроек можно добавить другие переменные и заголовки.

Список зависимостей перечислен в файле настроек, раздел **[build-system]** (устанавливаются из корня проекта по ```pip install .```). Бот пишется на python версии 3.11 (на 3.10 проверял - должен работать).

При любой непонятной или исключительной ситуации скрипт падает - проблему разбираем вручную, можно попробовать увеличить время ожидания запросов через переменную **request_timeout**. В *main.log* сохраняются все ответы json для анализа.
