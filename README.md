# dhqclash

[![Custom MRS release](https://img.shields.io/badge/release-custom--mrs-blue)](https://github.com/dashqee/dhqclash-public/releases/tag/custom-mrs)

Персональные Clash/Mihomo конфиги, выдаваемые через Telegram-бота
[@dhqclashconfigbot](https://t.me/dhqclashconfigbot), и открытый набор
пользовательских правил маршрутизации.

Исходный код бота и инфраструктуры приватный; здесь — только пользовательская
часть: как получить доступ, как предложить правило маршрутизации, и публичный
release со скомпилированными `.mrs` правилами.

---

## Как получить доступ

1. Откройте бота [@dhqclashconfigbot](https://t.me/dhqclashconfigbot) и отправьте `/start`.
2. Если конфигурация ещё не привязана — попросите у администратора одноразовый
   claim-код и отправьте:

   ```text
   /claim ВАШ-КОД
   ```

3. Бот пришлёт персональные subscription-ссылки — добавьте нужную как
   subscription URL в клиент Clash/Mihomo (по одной ссылке на каждое устройство).

Полезные команды бота: `/config` — повторно показать ссылки; `/rename <устройство> <имя>`
— переименовать устройство; `/router_config` — скрипт автообновления для роутера;
`/help` — список команд.

---

## Предложить правило маршрутизации

Правила задают, какие домены/адреса идут через прокси (`PROXY`), а какие напрямую
(`DIRECT`). Предложить своё правило можно через Issue-форму:

**[Создать запрос на custom routing rule](https://github.com/dashqee/dhqclash-public/issues/new?template=custom-routing-rule.yml)**

| Поле | Что указать | Пример |
|---|---|---|
| **Target** | `PROXY` (через прокси) или `DIRECT` (напрямую) | `PROXY` |
| **Domains or IP/CIDR** | домены, IP или CIDR, по одному на строку; без URL-схемы и Clash-синтаксиса | `youtube.com`<br>`149.154.160.0/20` |
| **Comment** | необязательное пояснение | `YouTube не открывается напрямую` |

Допустимые форматы записи:

```text
example.com     — домен и все его поддомены
*.example.com   — то же самое
1.1.1.1         — одиночный IP
8.8.8.8/32      — IP/CIDR
149.154.160.0/20
ozon            — «голое» имя: домен ozon с любыми поддоменами и любым TLD
                  (ozon.ru, www.ozon.com, cdn.x.ozon.travel — да; myozon.ru — нет)
```

Недопустимо: полные URL (`https://example.com/path`) и Clash-синтаксис
(`DOMAIN-SUFFIX,...`, `IP-CIDR,...`).

Запросы ревьюятся вручную. После одобрения правило попадает в сборку и
подтягивается всеми клиентами автоматически через rule-providers — отдельных
действий от вас не требуется.

---

## Маршрутизация приложений (по процессам)

Можно направить в прокси или напрямую целое **приложение** — по имени процесса,
а не по доменам. Форма отдельная:

**[Создать запрос на app routing rule](https://github.com/dashqee/dhqclash-public/issues/new?template=app-routing-rule.yml)**

| Поле | Что указать | Пример |
|---|---|---|
| **Target** | `PROXY` (через прокси) или `DIRECT` (напрямую) | `PROXY` |
| **Applications** | имена процессов / пакетов / путей, по одному на строку; без запятых и Clash-синтаксиса | `steam.exe`<br>`org.telegram.messenger` |
| **Comment** | необязательное пояснение | `Стим только напрямую` |

Допустимые форматы записи:

```text
steam.exe               — имя процесса (Windows)
Telegram                — имя процесса (macOS/Linux)
org.telegram.messenger  — имя пакета (Android)
path:/Applications/Foo.app/Contents/MacOS/Foo — по полному пути процесса
regex:^chrom(e|ium)     — по регулярному выражению на имя процесса
```

**Где работает:** Windows, macOS, Linux, Android (на Android матчится имя пакета).

**Где НЕ работает:** iOS — сетевое расширение не видит, какое приложение породило
трафик (ограничение платформы Apple). Чтобы направить приложение на iOS, добавьте
его **домены** через форму [custom routing rule](#предложить-правило-маршрутизации).

---

## Публичные правила (release `custom-mrs`)

Скомпилированные `.mrs` наборы правил лежат в
[release `custom-mrs`](https://github.com/dashqee/dhqclash-public/releases/tag/custom-mrs)
и обновляются автоматически при изменении списков:

- `custom-proxy-domains.mrs` / `custom-proxy-ipcidr.mrs` — идёт через прокси;
- `custom-local-domains.mrs` / `custom-local-ipcidr.mrs` — идёт напрямую;
- `custom-apps-proxy.list` / `custom-apps-local.list` — правила по процессам
  (classical/text, не `.mrs`; действуют на desktop и Android, не на iOS).

Конфигурации клиентов ссылаются на эти файлы как на rule-providers, так что
изменения применяются без переустановки подписки.

См. также [CHANGELOG](CHANGELOG.md).
