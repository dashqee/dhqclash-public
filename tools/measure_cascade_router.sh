#!/bin/sh
# Замер relay-каскада на роутере клиента (Keenetic + Entware + xkeen + mihomo).
#
# Наблюдает за РАБОЧИМ mihomo через его API и ничего в нём не меняет:
#   - каждые 30 с: история health-check'ов всех прокси и текущий выбор групп
#     (/proxies), число соединений и счётчики трафика, CPU/память роутера и
#     процесса mihomo;
#   - каждую минуту: TCP+TLS до каждого релея (curl, мимо прокси) и URL-тест
#     каждой цепочки с длинным таймаутом. Тест идёт на gstatic, а Fallback
#     проверяет cp.cloudflare.com: mihomo хранит «жив/мёртв» отдельно на каждый
#     URL, поэтому выбор Fallback тест не сдвигает.
#
# Нужны только sh и curl. Сырые данные складываются в архив, разбор делает
# tools/clients/analyze_router_measure.py на нашей стороне. В архив не попадают
# ни конфиг, ни UUID, ни secret: API mihomo их не отдаёт.
#
# Запуск:  sh measure_cascade_router.sh            # 30 минут
#          DURATION=600 sh measure_cascade_router.sh
# Во время замера один раз запустите спидтест с любого устройства в сети.
set -u

PATH="/opt/usr/sbin:/opt/usr/bin:/opt/sbin:/opt/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PATH

DURATION="${DURATION:-1800}"
INTERVAL="${INTERVAL:-30}"
ACTIVE_EVERY="${ACTIVE_EVERY:-2}"          # в тиках: 2 × 30 с = раз в минуту
CONFIG="${CONFIG:-/opt/etc/mihomo/config.yaml}"
TEST_URL="https%3A%2F%2Fwww.gstatic.com%2Fgenerate_204"
TEST_TIMEOUT_MS=15000

command -v curl >/dev/null 2>&1 || { echo "ERROR: нужен curl (opkg install curl)" >&2; exit 1; }
[ -r "$CONFIG" ] || { echo "ERROR: не найден конфиг mihomo: $CONFIG (задайте CONFIG=...)" >&2; exit 1; }

# external-controller: 0.0.0.0:9066  /  secret: 'abc'
yaml_value() {
  sed -n "s/^$1:[[:space:]]*//p" "$CONFIG" | head -n 1 | tr -d "\"'\r" | sed 's/[[:space:]]*#.*$//'
}
CONTROLLER="${CONTROLLER:-$(yaml_value external-controller)}"
SECRET="${SECRET:-$(yaml_value secret)}"
PORT="${CONTROLLER##*:}"
case "$PORT" in ''|*[!0-9]*) echo "ERROR: в $CONFIG нет external-controller" >&2; exit 1 ;; esac
API="http://127.0.0.1:$PORT"

api() { # api <path> [max-time]
  curl -sS --max-time "${2:-8}" -H "Authorization: Bearer $SECRET" "$API$1"
}

api /version >/dev/null 2>&1 || { echo "ERROR: API mihomo не отвечает на $API (xkeen запущен?)" >&2; exit 1; }

STAMP="$(date +%Y%m%d-%H%M%S)"
BASE="${OUT_BASE:-}"
[ -n "$BASE" ] || { [ -d /opt/tmp ] && BASE=/opt/tmp || BASE=/tmp; }
OUT="$BASE/dhq-measure-$STAMP"
ARCHIVE="$OUT.tar.gz"
mkdir -p "$OUT" || { echo "ERROR: не могу создать $OUT" >&2; exit 1; }

finish() {
  trap - EXIT HUP INT TERM
  date +%s >"$OUT/finished"
  ( cd "$BASE" && tar -czf "$ARCHIVE" "dhq-measure-$STAMP" ) 2>/dev/null && rm -rf "$OUT"
  echo
  if [ -f "$ARCHIVE" ]; then
    echo "Готово. Отправьте этот файл в поддержку DHQClash:"
    echo "  $ARCHIVE"
  else
    echo "Готово, но архив не собрался. Данные лежат в $OUT"
  fi
  exit 0
}
trap finish EXIT HUP INT TERM

# ---- контекст: железо и версии, без секретов -------------------------------
{
  echo "started=$(date +%s)"
  echo "date=$(date)"
  echo "duration=$DURATION interval=$INTERVAL active_every=$ACTIVE_EVERY"
  echo "uname=$(uname -a 2>/dev/null)"
  echo "ncpu=$(grep -c '^processor' /proc/cpuinfo 2>/dev/null || echo '?')"
  echo "cpu=$(grep -m1 -i -E 'model name|system type|cpu model|Hardware' /proc/cpuinfo 2>/dev/null)"
  echo "memtotal_kb=$(sed -n 's/^MemTotal:[[:space:]]*\([0-9]*\).*/\1/p' /proc/meminfo 2>/dev/null)"
  echo "mihomo=$(mihomo -v 2>/dev/null | head -n 1)"
  echo "mihomo_api=$(api /version 2>/dev/null)"
  echo "xkeen=$(xkeen -v 2>/dev/null | head -n 1)"
  if command -v ndmc >/dev/null 2>&1; then
    ndmc -c 'show version' 2>/dev/null | grep -i -E 'release|title|model|hw_id|device|arch' | sed 's/^[[:space:]]*/ndm /'
  fi
} >"$OUT/context.txt" 2>&1

# ---- релеи: "ip servername" из конфига (блочный и однострочный YAML) --------
awk '
  {
    line = $0
    if (match(line, /(^|[ {,])server:[ ]*[^ ,}]+/)) {
      s = substr(line, RSTART, RLENGTH); sub(/.*server:[ ]*/, "", s); gsub(/["\047]/, "", s)
    }
    if (match(line, /(^|[ {,])servername:[ ]*[^ ,}]+/)) {
      n = substr(line, RSTART, RLENGTH); sub(/.*servername:[ ]*/, "", n); gsub(/["\047]/, "", n)
      if (s ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ && n != "") print s, n
    }
  }
' "$CONFIG" | sort -u >"$OUT/relays.txt"

urlencode() { # каждый байт как %xx: в именах прокси эмодзи, пробелы и "|"
  printf '%s' "$1" | od -An -tx1 | tr -d '\n' | tr -s ' ' | sed 's/ $//; s/^\([^ ]\)/ \1/; s/ /%/g'
}

# Имена цепочек каскада: члены группы Fallback со стрелкой в имени.
chains() {
  api /proxies/Fallback 2>/dev/null \
    | sed -n 's/.*"all":\[\([^]]*\)\].*/\1/p' \
    | sed 's/^"//; s/"$//; s/","/\n/g' \
    | grep '→'
}

sample_sys() { # <ts>
  cpu="$(sed -n '1s/^cpu[[:space:]]*//p' /proc/stat 2>/dev/null)"
  pid="$(pidof mihomo 2>/dev/null | awk '{print $1}')"
  [ -n "$pid" ] || pid="$(pgrep -x mihomo 2>/dev/null | head -n 1)"
  ticks=""
  [ -n "$pid" ] && [ -r "/proc/$pid/stat" ] && ticks="$(awk '{print $14, $15, $24}' "/proc/$pid/stat" 2>/dev/null)"
  mem="$(sed -n 's/^MemAvailable:[[:space:]]*\([0-9]*\).*/\1/p' /proc/meminfo 2>/dev/null)"
  [ -n "$mem" ] || mem="$(sed -n 's/^MemFree:[[:space:]]*\([0-9]*\).*/\1/p' /proc/meminfo 2>/dev/null)"
  load="$(cut -d' ' -f1 /proc/loadavg 2>/dev/null)"
  api /connections 10 >"$OUT/.conn" 2>/dev/null
  conns="$(grep -o '"id":"' "$OUT/.conn" 2>/dev/null | wc -l | tr -d ' ')"
  down="$(head -c 400 "$OUT/.conn" 2>/dev/null | sed -n 's/.*"downloadTotal":\([0-9]*\).*/\1/p')"
  up="$(head -c 400 "$OUT/.conn" 2>/dev/null | sed -n 's/.*"uploadTotal":\([0-9]*\).*/\1/p')"
  rm -f "$OUT/.conn"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$cpu" "$ticks" "$mem" "$load" "$conns" "$down" "$up" >>"$OUT/sys.tsv"
}

sample_relays() { # <ts>
  while read -r ip name; do
    [ -n "$ip" ] || continue
    res="$(curl -sk -o /dev/null --max-time 10 --resolve "$name:443:$ip" \
      -w '%{time_connect} %{time_appconnect} %{http_code}' "https://$name/" 2>/dev/null)"
    printf '%s\t%s\t%s\n' "$1" "$ip" "${res:-fail}" >>"$OUT/relay.tsv"
  done <"$OUT/relays.txt"
}

sample_active() { # <ts>
  chains >"$OUT/.chains"
  while IFS= read -r chain; do
    [ -n "$chain" ] || continue
    res="$(api "/proxies/$(urlencode "$chain")/delay?url=$TEST_URL&timeout=$TEST_TIMEOUT_MS" 20 2>/dev/null)"
    printf '%s\t%s\t%s\n' "$(date +%s)" "$chain" "${res:-fail}" >>"$OUT/active.tsv"
  done <"$OUT/.chains"
  rm -f "$OUT/.chains"
}

echo "Замер идёт $((DURATION / 60)) мин. Роутером можно пользоваться как обычно."
echo "Один раз за это время запустите спидтест (speedtest.net или fast.com) с телефона или компьютера."
echo "Прервать: Ctrl+C — собранное сохранится."

START="$(date +%s)"
END=$((START + DURATION))
tick=0
while :; do
  now="$(date +%s)"
  [ "$now" -lt "$END" ] || break
  tick=$((tick + 1))
  n="$(printf '%04d' "$tick")"
  api /proxies 10 2>/dev/null | gzip -c >"$OUT/proxies-$n-$now.json.gz"
  sample_sys "$now"
  if [ $((tick % ACTIVE_EVERY)) -eq 1 ] || [ "$ACTIVE_EVERY" -le 1 ]; then
    sample_relays "$now"
    sample_active "$now"
  fi
  printf '\r  прошло %s из %s мин ' "$(( ($(date +%s) - START) / 60 ))" "$((DURATION / 60))"
  next=$((START + tick * INTERVAL))
  wait_s=$((next - $(date +%s)))
  [ "$wait_s" -gt 0 ] && sleep "$wait_s"
done
finish
