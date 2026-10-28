"""澶ц偉楸奸厤缃寘瀵煎叆宸ュ叿銆?
鎶?settings/pack.json 閲屽啓鐨勪笢瑗胯杩涗綘鐨?AstrBot锛氫汉鏍笺€佸叚涓彃浠跺拰瀹冧滑鐨勮缃€?琛ㄦ儏鍖呫€佽蹇嗐€佽闊筹紝杩樻湁 plugins/ 鏂囦欢澶归噷鐨勯澶栨彃浠躲€傚彲浠ュ弽澶嶈繍琛岋紝宸茬粡瑁呰繃鐨勪細璺宠繃鎴栨洿鏂般€?
鐢ㄦ硶锛氬弻鍑讳笂涓€灞傜殑銆屽鍏ュぇ鑲ラ奔.bat銆嶏紝鎸夋彁绀哄洖绛斿嚑涓棶棰樸€?娴嬭瘯鐢細python import_dafeiyu.py --answers 鍥炵瓟.json锛堝洖绛旀枃浠堕噷鐨?*_file 瀛楁鎸囧悜鏀惧瘑鐮佹垨 key 鐨勬枃鏈枃浠讹級銆?"""
import base64
import getpass
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANSWERS = {}
# Keep the persona limited to QQ-facing tools; never grant local computer tools.
PERSONA_TOOLS = [
    "search_memes",
    "llm_view_feed",
    "llm_publish_feed",
    "set_signature",
    "qqprofile_set_signature",
    "recall_long_term_memory",
]
# 琛ㄦ儏鍖呮彃浠朵笅 GitHub 鐢ㄧ殑鍔犻€熺珯锛屾寜椤哄簭璇曪紱鏈€鍚庣殑绌轰覆鏄洿杩?GitHub銆傚姞閫熺珯甯告崲甯告寕锛屾寕浜嗗線杩欓噷琛ユ柊鐨?GH_ACCELERATORS = ["https://ghfast.top/", ""]


def say(msg=""):
    print(msg, flush=True)


def step(msg):
    say(f"\n鈻?{msg}")


def warn(msg):
    say(f"  锛亄msg}")


def read_secret_file(path, key=None):
    lines = open(path, encoding="utf-8-sig").read().splitlines()
    if key:
        for line in lines:
            k, sep, v = line.replace("锛?, ":", 1).partition(":")  # 涓枃鍐掑彿涔熻
            if sep and k.strip().lower() == key:
                return v.strip()
    return lines[0].strip()


def ask(name, prompt, default=None, secret=False, choices=None):
    """闂竴涓棶棰橈紱--answers 妯″紡涓嬩粠鍥炵瓟鏂囦欢鍙栥€?""
    if name in ANSWERS:
        return str(ANSWERS[name])
    if f"{name}_file" in ANSWERS:
        return read_secret_file(ANSWERS[f"{name}_file"], ANSWERS.get(f"{name}_key"))
    if ANSWERS:
        if default is not None:
            return default
        sys.exit(f"鍥炵瓟鏂囦欢閲岀己 {name}")
    while True:
        hint = f"锛堢洿鎺ュ洖杞︾敤 {default}锛? if default not in (None, "") else ""
        text = f"{prompt}{hint}锛?
        value = getpass.getpass(text) if secret else input(text)
        value = value.strip() or (default or "")
        if choices and value not in choices:
            say(f"  璇疯緭鍏?{' / '.join(choices)} 閲岀殑涓€涓?)
            continue
        if value:
            return value


class Api:
    def __init__(self, base):
        self.root = base.rstrip("/")
        self.token = None

    def call(self, method, path, body=None, timeout=120, raw_body=None, content_type="application/json"):
        url = self.root + "/api/v1" + path
        data = raw_body if raw_body is not None else (
            json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None)
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", content_type)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read().decode("utf-8", "replace")
                code = r.status
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")
            code = e.code
        try:
            out = json.loads(text) if text else {}
        except ValueError:
            out = {"status": "error", "message": text[:300]}
        if not isinstance(out, dict):
            out = {"status": "ok", "data": out}
        out["_http"] = code
        return out

    @staticmethod
    def ok(r):
        return r.get("_http", 200) < 400 and r.get("status", "ok") != "error"

    @staticmethod
    def msg(r):
        return str(r.get("message") or r.get("detail") or r.get("data") or r)[:300]

    def login(self, user, password):
        for pw in (password, hashlib.md5(password.encode()).hexdigest()):
            r = self.call("POST", "/auth/login", {"username": user, "password": pw})
            data = r.get("data")
            if isinstance(data, dict) and data.get("token"):
                self.token = data["token"]
                return True
        return False


def get_path(d, dotted):
    for k in dotted.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def set_path(d, dotted, value):
    keys = dotted.split(".")
    for k in keys[:-1]:
        if not isinstance(d.get(k), dict):
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value


def fill(value, ctx):
    """鎶?{涓讳汉浼氳瘽}銆亄瀵硅瘽妯″瀷} 杩欑被鍗犱綅鎹㈡垚鐪熷€笺€?""
    if isinstance(value, str):
        for k, v in ctx.items():
            value = value.replace("{" + k + "}", v)
        return value
    if isinstance(value, list):
        return [fill(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: fill(v, ctx) for k, v in value.items()}
    return value


def launcher_data_dirs():
    """鍚姩鍣ㄧ殑鏁版嵁鐩綍锛氶粯璁ゅ湪鐢ㄦ埛鐩綍涓嬶紱鍦ㄥ惎鍔ㄥ櫒銆岄珮绾с€嶉噷鏀硅繃鐨勶紝璁板湪 APPDATA 涓嬬殑璁剧疆鏂囦欢閲屻€?""
    dirs = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        try:
            d = json.load(open(os.path.join(appdata, "com.github.raven95676.astrbot-launcher", ".data-dir.json"),
                               encoding="utf-8-sig")).get("data_dir", "").strip()
            if d:
                dirs.append(d)
        except Exception:
            pass
    dirs.append(os.path.join(os.path.expanduser("~"), ".astrbot_launcher"))
    return dirs


def find_instances():
    """鍚姩鍣ㄥ悇瀹炰緥閰嶇疆閲屽啓鐨勫悗鍙扮鍙ｏ紙鍚姩鍣ㄥ父鍙︾粰绔彛锛岃繖涓彧褰撳€欓€夛級銆?""
    found = []
    cfgs = []
    for data_dir in launcher_data_dirs():
        cfgs += glob.glob(os.path.join(data_dir, "instances", "*", "core", "data", "cmd_config.json"))
    for cfg in cfgs:
        try:
            port = json.load(open(cfg, encoding="utf-8-sig")).get("dashboard", {}).get("port")
        except Exception:
            continue
        if port:
            found.append((cfg.split(os.sep)[-4], int(port)))
    return found


def python_listening_ports():
    """鏈満 python 杩涚▼姝ｅ湪鐩戝惉鐨勭鍙ｏ紙AstrBot 鍚庡彴涓€瀹氬湪閲岄潰锛夈€傛嬁涓嶅埌灏辫繑鍥炵┖銆?""
    ports = set()
    try:
        if os.name == "nt":
            names = {}
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                                 timeout=15, errors="replace").stdout
            for line in out.splitlines():
                cols = [c.strip('"') for c in line.split('","')]
                if len(cols) > 1:
                    names[cols[1]] = cols[0].lower()
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                                 timeout=15, errors="replace").stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
                    host, _, port = parts[1].rpartition(":")
                    if host in ("127.0.0.1", "0.0.0.0") and names.get(parts[4], "").startswith("python"):
                        ports.add(int(port))
        else:
            out = subprocess.run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], capture_output=True, text=True,
                                 timeout=15, errors="replace").stdout
            for line in out.splitlines():
                if line.lower().startswith("python") and "(LISTEN)" in line:
                    addr = line.split()[-2]
                    host, _, port = addr.rpartition(":")
                    if host in ("127.0.0.1", "*", "localhost") and port.isdigit():
                        ports.add(int(port))
    except Exception:
        pass
    return ports


def is_astrbot_dashboard(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as r:
            return "AstrBot" in r.read(65536).decode("utf-8", "replace")
    except Exception:
        return False


def pick_backend():
    if "base_url" in ANSWERS:
        return ANSWERS["base_url"]
    candidates = sorted({port for _, port in find_instances()} | python_listening_ports())
    alive = [port for port in candidates if is_astrbot_dashboard(port)]
    if not alive:
        # 鍏滃簳锛氭壂涓€閬?AstrBot 鍜屽惎鍔ㄥ櫒甯哥敤鐨勭鍙ｆ
        alive = [port for port in [*range(6185, 6201), *range(18600, 18621)]
                 if port not in candidates and is_astrbot_dashboard(port)]
    if len(alive) > 1:
        say("  鎵惧埌濂藉嚑涓鍦ㄨ繍琛岀殑 AstrBot锛? + "銆?.join(f"127.0.0.1:{p}" for p in alive))
    default = f"http://127.0.0.1:{alive[0]}" if alive else "http://127.0.0.1:6185"
    url = ask("base_url", "AstrBot 鍚庡彴鍦板潃锛堟祻瑙堝櫒閲屾墦寮€鍚庡彴鏃跺湴鍧€鏍忛偅涓诧級", default)
    if not url.startswith("http"):
        url = "http://" + url
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def upsert_provider(api, conf):
    pid = conf["id"]
    existing = provider_config(api, pid)
    if existing:
        merged = {**existing, **conf}
        r = api.call("PUT", f"/providers/{urllib.parse.quote(pid, safe='')}", {"config": merged})
    else:
        r = api.call("POST", "/providers", {"config": conf})
    if not api.ok(r):
        warn(f"淇濆瓨銆寋pid}銆嶅け璐ワ細{api.msg(r)}")
        return False
    return True


def provider_config(api, pid):
    """璇讳竴涓ā鍨嬫彁渚涘晢鐨勯厤缃紱娌℃湁灏辫繑鍥?None銆?""
    r = api.call("GET", f"/providers/{urllib.parse.quote(pid, safe='')}")
    data = r.get("data") if api.ok(r) and isinstance(r.get("data"), dict) else {}
    data = data.get("provider", data)
    return data if isinstance(data, dict) and data.get("id") == pid else None


def test_provider(api, pid):
    r = api.call("POST", "/providers/test", {"provider_id": pid}, timeout=90)
    data = r.get("data") if isinstance(r.get("data"), dict) else {}
    status = str(data.get("status") or r.get("status") or "")
    if api.ok(r) and status not in ("error", "unavailable", "failed"):
        return True, ""
    return False, str(data.get("error") or data.get("message") or api.msg(r))[:200]


def extra_plugins():
    root = os.path.join(PACK, "plugins")
    zips = glob.glob(os.path.join(root, "*.zip"))
    dirs = [d for d in glob.glob(os.path.join(root, "*")) if os.path.isfile(os.path.join(d, "metadata.yaml"))]
    return sorted(zips + dirs)


def plugin_name(path):
    meta = os.path.join(path, "metadata.yaml")
    if os.path.isfile(meta):
        for line in open(meta, encoding="utf-8-sig"):
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip().strip("'\"")
    return ""


def zip_folder(folder):
    import io
    import zipfile
    buf = io.BytesIO()
    top = os.path.basename(folder.rstrip("\\/"))
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for f in filenames:
                if f.endswith(".pyc"):
                    continue
                full = os.path.join(dirpath, f)
                zf.write(full, os.path.join(top, os.path.relpath(full, folder)))
    return buf.getvalue()


def multipart(field, filename, payload):
    boundary = uuid.uuid4().hex
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\n"
            "Content-Type: application/zip\r\n\r\n").encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode()
    return head + payload + tail, f"multipart/form-data; boundary={boundary}"


def main():
    global ANSWERS
    if "--answers" in sys.argv:
        ANSWERS = json.load(open(sys.argv[sys.argv.index("--answers") + 1], encoding="utf-8-sig"))
    pack = json.load(open(os.path.join(PACK, "settings", "pack.json"), encoding="utf-8-sig"))
    say("澶ц偉楸奸厤缃寘瀵煎叆宸ュ叿")
    say("寮€濮嬪墠纭锛欰strBot 宸茬粡鍦ㄨ繍琛岋紝QQ 灏忓彿宸茬粡閫氳繃 NapCat 鎺ヤ笂锛孌eepSeek 宸茬粡鑳芥甯稿洖璇濄€?)

    # ---------- 杩炴帴鍚庡彴 ----------
    api = Api(pick_backend())
    user = ask("username", "鍚庡彴璐﹀彿", "astrbot")
    password = ask("password", "鍚庡彴瀵嗙爜锛堣緭鍏ユ椂涓嶆樉绀猴級", secret=True)
    if not api.login(user, password):
        sys.exit("鐧诲綍澶辫触锛氭鏌ュ悗鍙板湴鍧€銆佽处鍙枫€佸瘑鐮併€?)
    say("  宸茬櫥褰曞悗鍙?)

    owner = ask("owner_qq", "浣犺嚜宸辩殑 QQ 鍙凤紙澶у彿锛屽ス浼氭妸瀹冨綋涓讳汉锛?)
    if not owner.isdigit():
        sys.exit("QQ 鍙峰彧鑳芥槸鏁板瓧")
    say("\n璁板繂浜岄€変竴锛? 鏈満 Ollama锛堝厤璐癸紝瑕佸厛瑁?Ollama锛? 2 纭呭熀娴佸姩锛堣涓€涓鍩烘祦鍔ㄧ殑 key锛? 0 鍏堜笉瑁?)
    memory = ask("memory", "閫?, "2", choices=["0", "1", "2"])
    sf_key = ask("siliconflow_key", "纭呭熀娴佸姩 key锛堣緭鍏ユ椂涓嶆樉绀猴級", secret=True) if memory == "2" else ""
    say("\n璇煶閫変竴涓細3 璞嗗寘 Seed Audio锛堟帹鑽愶紝瑕佺伀灞卞紩鎿庤眴鍖呰闊崇殑 APP ID 鍜?Access Token锛屾寜璇煶鏃堕暱绾?1 鍏?鍒嗛挓锛?
        "  4 鏈満 Breeze锛堝厤璐癸紝鏄惧崱鍦ㄦ湰鏈虹畻锛屽厛鐢ㄣ€岃Breeze璇煶.bat銆嶃€屽仛澹伴煶.bat銆嶈濂姐€佸仛濂藉０闊筹級"
        "  1 寰蒋 Edge 鍏嶈垂濂冲０  2 灏忕背 MiMo 鍏嬮殕闊筹紙瑕?MiMo 鐨?key锛? 0 鍏堜笉寮€")
    voice = ask("voice", "閫?, "3", choices=["0", "1", "2", "3", "4"])
    mimo_key = ask("mimo_key", "MiMo key锛堣緭鍏ユ椂涓嶆樉绀猴級", secret=True) if voice == "2" else ""
    volc_app_id = volc_token = ""
    volc_api_key = ""
    if voice == "3":
        volc_api_key = ask("volc_api_key", "璞嗗寘璇煶鏂扮増 API Key锛堟柊鐗堟帶鍒跺彴锛涜緭鍏ユ椂涓嶆樉绀猴級", secret=True)
        if not volc_api_key:
            volc_app_id = ask("volc_app_id", "璞嗗寘璇煶鏃х増 APP ID")
            volc_token = ask("volc_access_token", "璞嗗寘璇煶鏃х増 Access Token锛堣緭鍏ユ椂涓嶆樉绀猴級", secret=True)

    r = api.call("GET", "/config-profiles/default")
    cfg = (r.get("data") or {}).get("config") if isinstance(r.get("data"), dict) else None
    if not isinstance(cfg, dict):
        sys.exit(f"璇讳笉鍒伴厤缃細{api.msg(r)}")

    platforms = [p for p in cfg.get("platform", []) if p.get("type") == "aiocqhttp"]
    platforms.sort(key=lambda p: not p.get("enable", True))
    if not platforms:
        sys.exit("鍚庡彴閲岃繕娌℃湁 QQ 鏈哄櫒浜猴紙OneBot v11锛夛紝鍏堟寜瑙嗛鎺ュソ NapCat 鍐嶆潵銆?)
    platform_id = platforms[0]["id"]
    chat_id = get_path(cfg, "agent_runner.config.model.provider_id") or ""
    if not chat_id:
        chats = [p for p in cfg.get("provider", []) if p.get("provider_type", "chat_completion") == "chat_completion" and p.get("enable", True)]
        chat_id = chats[0]["id"] if chats else ""
    if not chat_id:
        sys.exit("鍚庡彴閲岃繕娌℃湁瀵硅瘽妯″瀷锛屽厛鎸夎棰戞帴濂?DeepSeek 鍐嶆潵銆?)
    session = f"{platform_id}:FriendMessage:{owner}"
    ctx = {"涓讳汉浼氳瘽": session, "瀵硅瘽妯″瀷": chat_id, "鍞辨瓕鍚庣": (pack.get("sing") or {}).get("backend") or "doubao"}
    say(f"  鏈哄櫒浜猴細{platform_id}銆€瀵硅瘽妯″瀷锛歿chat_id}")
    results = []

    # ---------- 瀵硅瘽妯″瀷锛氬叧鎬濊€冿紝鍥炲緱蹇?----------
    step("璋冩暣瀵硅瘽妯″瀷")
    prov = provider_config(api, chat_id)
    if prov and "deepseek" in (str(prov.get("model", "")) + str(prov.get("provider_source_id", ""))).lower():
        extra = dict(prov.get("custom_extra_body") or {})
        extra.update(pack["chat_model"]["custom_extra_body"])
        prov["custom_extra_body"] = extra
        ok = api.ok(api.call("PUT", f"/providers/{urllib.parse.quote(chat_id, safe='')}", {"config": prov}))
        say("  宸插叧闂繁搴︽€濊€冿紝鍥炲緱鏇村揩" if ok else "  锛佹病鏀规垚锛屼笉褰卞搷浣跨敤")
    else:
        say("  涓嶆槸 DeepSeek 妯″瀷锛岃烦杩?)

    # ---------- 浜烘牸 ----------
    step("鍐欏叆浜烘牸銆屽ぇ鑲ラ奔銆?)
    pid = pack["persona"]["id"]
    text = open(os.path.join(PACK, pack["persona"]["file"]), encoding="utf-8-sig").read().replace("{OWNER_QQ}", owner)
    qid = urllib.parse.quote(pid, safe="")
    cur = api.call("GET", f"/personas/{qid}")
    if api.ok(cur) and isinstance(cur.get("data"), dict) and cur["data"].get("persona_id") == pid:
        body = {k: v for k, v in cur["data"].items() if k in ("begin_dialogs", "skills", "folder_id", "sort_order", "custom_error_message")}
        body.update({"system_prompt": text, "tools": PERSONA_TOOLS})
        r = api.call("PUT", f"/personas/{qid}", body)
    else:
        r = api.call("POST", "/personas", {"persona_id": pid, "system_prompt": text, "begin_dialogs": [], "tools": PERSONA_TOOLS})
    results.append(("浜烘牸", api.ok(r)))
    say("  瀹屾垚" if api.ok(r) else f"  锛佸け璐ワ細{api.msg(r)}")

    # ---------- 鎻掍欢 ----------
    step("浠庢彃浠跺競鍦哄畨瑁呮彃浠讹紙绗竴娆¤涓嬭浇锛屾參鐨勮瘽绛変竴涓ゅ垎閽燂級")
    installed = {p.get("name") for p in (api.call("GET", "/plugins").get("data") or []) if isinstance(p, dict)}
    for p in pack["plugins"]:
        if p["name"] in installed:
            say(f"  {p['name']}锛氬凡瑁呰繃")
            continue
        say(f"  {p['name']}锛氬畨瑁呬腑鈥︼紙{p['what']}锛?)
        r = api.call("POST", "/plugins/install/github",
                     {"install_method": "market", "market_plugin_id": p["market_id"]}, timeout=600)
        if not api.ok(r):
            warn(f"瑁呬笉涓婏細{api.msg(r)}")
            warn("鎻掍欢鏄粠鎻掍欢甯傚満鐨勬湇鍔″櫒涓嬬殑锛屽彲鑳戒竴鏃舵病鍝嶅簲銆傜瓑鍑犲垎閽熷啀杩愯涓€娆℃湰宸ュ叿锛涜繕瑁呬笉涓婏紝灏卞湪鍚庡彴銆屾彃浠?鈫?鎻掍欢甯傚満銆嶉噷鎼滆繖涓彃浠舵墜鍔ㄨ锛岃濂藉啀杩愯涓€娆°€?)
    installed = {p.get("name") for p in (api.call("GET", "/plugins").get("data") or []) if isinstance(p, dict)}
    for p in pack["plugins"]:
        results.append((f"鎻掍欢 {p['name']}", p["name"] in installed))

    # 棰濆鎻掍欢锛堟瘮濡傝眴鍖呰闊筹級锛歱lugins/ 閲岀殑 zip锛屾垨甯?metadata.yaml 鐨勬彃浠舵枃浠跺す
    for z in extra_plugins():
        base = z[:-4] if z.endswith(".zip") else z
        meta_path = base + ".json"
        meta = json.load(open(meta_path, encoding="utf-8-sig")) if os.path.exists(meta_path) else {}
        name = meta.get("name") or plugin_name(z) or os.path.basename(base)
        if meta.get("only_with_voice") and meta["only_with_voice"] != voice and name not in installed:
            continue
        if name in installed and not meta.get("always_reinstall"):
            say(f"  {name}锛氬凡瑁呰繃")
        else:
            say(f"  {name}锛氫粠閰嶇疆鍖呭畨瑁呪€?)
            payload = open(z, "rb").read() if z.endswith(".zip") else zip_folder(z)
            body, ctype = multipart("file", os.path.basename(base) + ".zip", payload)
            r = api.call("POST", "/plugins/install/upload", raw_body=body, content_type=ctype, timeout=600)
            if not api.ok(r):
                warn(f"瑁呬笉涓婏細{api.msg(r)}")
        if meta.get("config"):
            pack["plugins"].append({"name": name, "config": meta["config"], "what": meta.get("what", "")})
        installed = {p.get("name") for p in (api.call("GET", "/plugins").get("data") or []) if isinstance(p, dict)}
        results.append((f"鎻掍欢 {name}", name in installed))

    step("鏀规彃浠惰缃?)
    changed = []
    for p in pack["plugins"]:
        if p["name"] not in installed or not p["config"]:
            continue
        r = api.call("GET", f"/plugins/config?plugin_id={urllib.parse.quote(p['name'])}")
        conf = (r.get("data") or {}).get("config") if isinstance(r.get("data"), dict) else None
        if not isinstance(conf, dict):
            warn(f"{p['name']}锛氳涓嶅埌璁剧疆")
            continue
        for k, v in p["config"].items():
            if get_path(conf, k) is None and "." in k and get_path(conf, k.rsplit(".", 1)[0]) is None:
                warn(f"{p['name']}锛氳缃」 {k} 涓嶅瓨鍦紝鍙兘鎻掍欢鏇存柊鏀瑰悕浜嗭紝璺宠繃")
                continue
            set_path(conf, k, fill(v, ctx))
        r = api.call("PUT", "/plugins/config", {"plugin_id": p["name"], "config": conf})
        say(f"  {p['name']}锛歿'瀹屾垚' if api.ok(r) else '澶辫触 ' + api.msg(r)}")
        if api.ok(r):
            changed.append(p["name"])

    for tool, perm in pack["tool_permissions"].items():
        r = api.call("PATCH", f"/tools/{urllib.parse.quote(tool, safe='')}/permission", {"permission": perm})
        if not api.ok(r):
            warn(f"宸ュ叿 {tool} 鏉冮檺娌℃敼鎴愶細{api.msg(r)}")
    say("  鍙戠┖闂淬€佹敼绛惧悕鍙惉涓讳汉鐨勶細宸茶缃?)

    # ---------- 琛ㄦ儏鍖?----------
    step("涓嬭浇琛ㄦ儏鍖咃紙浠庤〃鎯呭寘鎻掍欢鐨勮祫婧愬箍鍦轰笅锛屽嚑鐧惧紶鍥撅紝瑕佷竴浼氬効锛?)
    if "meme_manager" in installed:
        ext = "/plugins/extensions/meme_manager"
        # 琛ㄦ儏鍖呬粠 GitHub 涓嬶紝缁忔彃浠堕噷璁剧殑鍔犻€熺珯锛涘姞閫熺珯鏃跺ソ鏃跺潖锛屼笅涓嶅姩灏辨崲涓嬩竴涓啀璇?        cur = meme_accelerator(api)
        accels = ([cur] if cur and cur not in GH_ACCELERATORS else []) + GH_ACCELERATORS
        ai, gh_warned = 0, False
        if cur != accels[0]:
            meme_accelerator(api, accels[0])
        api.call("POST", f"{ext}/community/index/fetch", {}, timeout=120)
        have = meme_pack_ids(api, ext)
        for mp in pack["meme_packs"]:
            if mp["id"] in have:
                say(f"  {mp['id']}锛氬凡鏈?)
                results.append((f"琛ㄦ儏鍖?{mp['id']}", True))
                continue
            while True:
                r = api.call("POST", f"{ext}/community/install",
                             {"pack_id": mp["id"], "set_as_default": mp["default"]}, timeout=900)
                ok = api.ok(r)
                if ok or ai + 1 >= len(accels):
                    break
                ai += 1
                say(f"  {mp['id']}锛氭病涓嬩笅鏉ワ紙{api.msg(r)[:80]}锛夛紝鎹釜 GitHub 鍔犻€熷湴鍧€鍐嶈瘯锛歿accels[ai] or '鐩磋繛 GitHub'}")
                if meme_accelerator(api, accels[ai]) is None:
                    break
                api.call("POST", f"{ext}/community/index/fetch", {}, timeout=120)
            say(f"  {mp['id']}锛歿'瀹屾垚' if ok else '澶辫触 ' + api.msg(r)}")
            results.append((f"琛ㄦ儏鍖?{mp['id']}", ok))
            if not ok and not gh_warned:
                gh_warned = True
                warn("鍑犱釜鍔犻€熷湴鍧€閮芥病涓嬩笅鏉ワ紝澶氬崐鏄繖浼氬効杩炰笉涓?GitHub銆傝繃涓€闃靛啀杩愯涓€娆℃湰宸ュ叿锛?
                     "鎴栬€呭湪鍚庡彴銆屾彃浠?鈫?meme_manager 鈫?閰嶇疆銆嶉噷鎶?GitHub 鍔犻€熷湴鍧€鎹㈡垚浣犺兘鐢ㄧ殑锛屽啀杩愯涓€娆°€?)
        # 榛樿瑙勫垯鍐欐垚銆屽嚑濂椾竴璧风敤銆嶏細meme_manager 鐨勯€夋嫨瑙勫垯鏀寔 pack_ids 鍒楄〃锛屼富濂楁帓绗竴
        use = [mp["id"] for mp in sorted(pack["meme_packs"], key=lambda m: not m.get("default"))
               if mp.get("use", True)]
        ok = bool(use) and meme_use_together(api, ext, use)
        if not ok:
            # 瑙勫垯鎺ュ彛鐢ㄤ笉浜嗭紙姣斿鎻掍欢鐗堟湰澶€侊級锛氶€€鍥炲彧璁句富濂椾负榛樿
            main = next((mp["id"] for mp in pack["meme_packs"] if mp.get("default")), None)
            if main:
                ok = api.ok(api.call("POST", f"{ext}/packs/default", {"pack_id": main}))
                say(f"  鍙妸 {main} 璁炬垚榛樿锛歿'瀹屾垚' if ok else '澶辫触'}")
        results.append(("琛ㄦ儏鍖呴粯璁ょ敤鐨勫嚑濂?, ok))
    else:
        results.append(("琛ㄦ儏鍖?, False))

    # ---------- 璁板繂 ----------
    step("璁板繂")
    lm = "astrbot_plugin_livingmemory"
    mem_ok = False
    if memory == "0":
        say("  鍏堜笉瑁呫€備互鍚庢兂瑁咃紝鍐嶈繍琛屼竴娆℃湰宸ュ叿閫?1 鎴?2銆?)
    else:
        m = pack["memory"]
        if memory == "1":
            o = m["ollama"]
            if not ollama_ready(o["ollama_model"]):
                warn("Ollama 娌″湪杩愯鎴栨ā鍨嬫病涓嬪ソ锛屽厛璺宠繃璁板繂銆傝濂?Ollama 鍚庡啀杩愯涓€娆℃湰宸ュ叿銆?)
                o = None
            conf = o and {"id": o["id"], "embedding_api_key": o["embedding_api_key"],
                          "embedding_api_base": o["embedding_api_base"], "embedding_model": o["embedding_model"]}
        else:
            s = m["siliconflow"]
            conf = {"id": s["id"], "embedding_api_key": sf_key, "embedding_api_base": s["embedding_api_base"],
                    "embedding_model": s["embedding_model"]}
        if conf and lm in installed:
            conf.update({"type": "openai_embedding", "provider": "openai", "provider_type": "embedding", "enable": True,
                         "embedding_dimensions": m["embedding_dimensions"], "embedding_dimensions_mode": "auto",
                         "timeout": 20, "proxy": ""})
            if upsert_provider(api, conf):
                good, why = test_provider(api, conf["id"])
                if not good:
                    warn(f"璁板繂妯″瀷娴嬭瘯娌￠€氳繃锛歿why}")
                r = api.call("GET", f"/plugins/config?plugin_id={lm}")
                lconf = (r.get("data") or {}).get("config")
                if isinstance(lconf, dict):
                    set_path(lconf, "provider_settings.embedding_provider_id", conf["id"])
                    mem_ok = api.ok(api.call("PUT", "/plugins/config", {"plugin_id": lm, "config": lconf})) and good
                    changed.append(lm)
    if lm in installed:
        api.call("PATCH", "/plugins/enabled", {"plugin_id": lm, "enabled": mem_ok})
        say("  璁板繂宸叉墦寮€" if mem_ok else "  璁板繂鎻掍欢鍏堝叧鐫€锛堟病閰嶅ソ璁板繂妯″瀷鏃跺紑鐫€浼氭姤閿欙級")
    if memory != "0":
        results.append(("璁板繂", mem_ok))

    # ---------- 璇煶 ----------
    step("璇煶")
    v = pack["voice"]
    tts_id = ""
    if voice == "1":
        e = v["edge"]
        for pkg in e["pip"]:
            say(f"  瀹夎 {pkg.split('==')[0]}鈥?)
            r = api.call("POST", "/pip/install", {"package": pkg}, timeout=600)
            if not api.ok(r):
                warn(f"瑁呬笉涓婏細{api.msg(r)}")
        conf = {"id": e["id"], "type": "edge_tts", "provider": "microsoft", "provider_type": "text_to_speech",
                "enable": True, "voice": e["voice"], "rate": "+0%", "volume": "+0%", "pitch": "+0Hz",
                "timeout": 20, "proxy": ""}
        tts_id = e["id"] if upsert_provider(api, conf) else ""
    elif voice == "2":
        mm = v["mimo"]
        ref = os.path.join(PACK, mm["reference_audio"])
        if not os.path.exists(ref):
            found = [f for f in sorted(glob.glob(os.path.join(PACK, "voice", "*"))) if f.lower().endswith((".mp3", ".wav", ".m4a"))]
            ref = found[0] if found else ref
        if not os.path.exists(ref):
            ref = ask("reference_audio", "閰嶇疆鍖呴噷娌℃湁鍙傝€冮煶锛岀粰涓€娈典綘鎯冲厠闅嗙殑澹伴煶鏂囦欢璺緞锛坢p3/wav锛?鈥?0 绉掞級").strip('"')
        ext = os.path.splitext(ref)[1].lower().lstrip(".") or "mp3"
        mime = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4"}.get(ext, "audio/mpeg")
        data_uri = f"data:{mime};base64," + base64.b64encode(open(ref, "rb").read()).decode()
        conf = {"id": mm["id"], "type": "mimo_tts_api", "provider": "mimo", "provider_type": "text_to_speech",
                "enable": True, "api_key": mimo_key, "api_base": mm["api_base"], "model": mm["model"],
                "mimo-tts-voice": data_uri, "mimo-tts-format": "wav", "mimo-tts-style-prompt": "",
                "mimo-tts-dialect": "", "mimo-tts-seed-text": "", "timeout": 30, "proxy": ""}
        tts_id = mm["id"] if upsert_provider(api, conf) else ""
    elif voice == "3":
        d = v["doubao"]
        if d["plugin"] not in installed:
            warn(f"璞嗗寘璇煶瑕佺殑鎻掍欢 {d['plugin']} 娌¤涓婏紝鍏堣烦杩囪闊炽€?)
        else:
            if volc_api_key:
                conf = {"id": d["id"], "type": "seed_audio_tts", "provider": "volcengine", "provider_type": "text_to_speech",
                        "enable": True, "api_key": volc_api_key, "app_id": "", "access_key": "", "credentials_file": "",
                        "api_base": "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse",
                        "resource_id": "seed-tts-2.0", "model": "seed-tts-2.0",
                        "seed_audio_speaker": "zh_female_tianmeitaozi_uranus_bigtts",
                        "seed_audio_speech_rate": -5, "seed_audio_loudness_rate": 1, "seed_audio_pitch": 2,
                        "seed_audio_format": d["format"], "seed_audio_sample_rate": d["sample_rate"],
                        "seed_audio_max_attempts": d["max_attempts"],
                        "seed_audio_whole_reply": d.get("whole_reply", True),
                        "seed_audio_reply_probability": v["trigger_probability"], "timeout": d["timeout"]}
            else:
                conf = {"id": d["id"], "type": "seed_audio_tts", "provider": "volcengine", "provider_type": "text_to_speech",
                        "enable": True, "app_id": volc_app_id, "access_key": volc_token, "credentials_file": "",
                        "api_base": d["api_base"], "resource_id": d["resource_id"], "model": d["model"],
                        "seed_audio_speaker": "zh_female_tianmeitaozi_uranus_bigtts",
                        "seed_audio_speech_rate": -5, "seed_audio_loudness_rate": 1, "seed_audio_pitch": 2,
                        "seed_audio_persona": d["persona"], "seed_audio_prompt_template": d["prompt_template"],
                        "seed_audio_format": d["format"], "seed_audio_sample_rate": d["sample_rate"],
                        "seed_audio_max_attempts": d["max_attempts"],
                        "seed_audio_whole_reply": d.get("whole_reply", True),
                        "seed_audio_reply_probability": v["trigger_probability"], "timeout": d["timeout"]}
            say("  璇曞康涓€鍙ャ€屼綘濂藉憖銆嶏紝璞嗗寘瑕佸崄鍑犵鈥?)
            tts_id = d["id"] if upsert_provider(api, conf) else ""
    elif voice == "4":
        bz = v["breeze"]
        try:
            with urllib.request.urlopen(bz["api_base"] + "/voices", timeout=10) as r:
                have = [x.get("id") for x in json.loads(r.read() or b"[]")]
        except Exception:
            have = None
        if have is None:
            warn("杩炰笉涓婃湰鏈虹殑 Breeze銆傚厛鍙屽嚮妗岄潰鐨勩€屽惎鍔˙reeze璇煶銆嶏紝娌¤鐨勮瘽鍏堝弻鍑汇€岃Breeze璇煶.bat銆嶃€?)
        elif bz["voice"] not in have:
            warn(f"Breeze 閲岃繕娌℃湁鍙?{bz['voice']} 鐨勫０闊筹紝鍏堝弻鍑汇€屽仛澹伴煶.bat銆嶅仛涓€涓€?)
        else:
            conf = {"id": bz["id"], "type": "openai_tts_api", "provider": "openai", "provider_type": "text_to_speech",
                    "enable": True, "api_key": "unused", "api_base": bz["api_base"], "model": "tts-1",
                    "openai-tts-voice": bz["voice"], "timeout": 180, "proxy": ""}
            say("  璇曞康涓€鍙ワ紝Breeze 瑕佸嚑绉掆€?)
            tts_id = bz["id"] if upsert_provider(api, conf) else ""
    if voice != "3":
        # 浠ュ墠閫夎繃璞嗗寘鍙堟崲浜嗗埆鐨勶細璞嗗寘鎻掍欢鍙鐪嬪埌瀹冪殑鎻愪緵鍟嗗紑鐫€灏变細鎺烽瀛愬彂鏁存潯璇煶锛屽緱鍏虫帀
        old = provider_config(api, v["doubao"]["id"])
        if old and old.get("enable"):
            upsert_provider(api, {**old, "enable": False})
            say("  涔嬪墠寮€鐫€鐨勮眴鍖呰闊冲凡鍏虫帀")
    if tts_id:
        good, why = test_provider(api, tts_id)
        if good:
            say(f"  璇煶宸叉墦寮€锛屽ぇ绾︿笁鏉″洖澶嶉噷鏈変竴鏉′細鍙戣闊?)
            if voice == "3":
                say("  璞嗗寘鏄暣鏉″洖澶嶅悎鎴愪竴鏉¤闊筹紝瑕佺瓑 15鈥?5 绉掓墠鍒?)
        else:
            # 娴嬩笉閫氬氨鍏堝叧鐫€锛氬紑鐫€鐨勮瘽濂规瘡鍙戜竴娆¤闊抽兘浼氭姤閿?            warn(f"璇煶娴嬭瘯娌￠€氳繃锛歿why}")
            if voice == "1" and re.search(r"WinError 2|鎵句笉鍒版寚瀹氱殑鏂囦欢|ffmpeg", why, re.I):
                warn("Edge 璇煶瑕佺敤 ffmpeg 杞牸寮忥紝杩欏彴鐢佃剳涓婂鍗婃病瑁呫€傚湪 PowerShell 閲岃繍琛?"
                     "winget install Gyan.FFmpeg 瑁呬笂锛岄噸鍚?AstrBot锛屽啀杩愯涓€娆℃湰宸ュ叿銆?)
            conf["enable"] = False
            upsert_provider(api, conf)
            tts_id = ""
            say("  璇煶鍏堝叧鐫€锛屽鐞嗗ソ鍐嶈繍琛屼竴娆℃湰宸ュ叿")
        results.append(("璇煶", good))
    elif voice != "0":
        results.append(("璇煶", False))
    else:
        say("  鍏堜笉寮€")

    # ---------- 鍏ㄥ眬璁剧疆 ----------
    step("鏀瑰叏灞€璁剧疆锛堝垎娈靛洖澶嶃€佽寰椾富浜恒€侀粯璁や汉鏍肩瓑锛?)
    r = api.call("GET", "/config-profiles/default")
    cfg = r["data"]["config"]
    for k, val in pack["base"].items():
        set_path(cfg, k, fill(val, ctx))
    ps = cfg.setdefault("platform_settings", {})
    if ps.get("enable_id_white_list"):
        wl = ps.setdefault("id_whitelist", [])
        if session not in wl and owner not in wl:
            wl.append(session)
    admins = cfg.setdefault("admins_id", [])
    if owner not in admins:
        admins.append(owner)
    tts = cfg.setdefault("provider_tts_settings", {})
    if tts_id and voice == "3" and v["doubao"].get("whole_reply", True):
        # 鏁存潯璇煶鐢辫眴鍖呮彃浠舵幏楠板瓙銆佷竴娆″悎鎴愶紱AstrBot 鑷繁鐨勬寜娈佃闊宠鍏虫帀锛屼笉鐒朵細鍐嶆寜娈佃浆涓€閬?        tts.update({"enable": False, "provider_id": tts_id, "trigger_probability": v["trigger_probability"]})
    elif tts_id:
        tts.update({"enable": True, "provider_id": tts_id, "trigger_probability": v["trigger_probability"]})
    else:
        tts["enable"] = False
    r = api.call("PUT", "/config-profiles/default", cfg)
    results.append(("鍏ㄥ眬璁剧疆", api.ok(r)))
    say("  瀹屾垚" if api.ok(r) else f"  锛佸け璐ワ細{api.msg(r)}")

    step("閲嶆柊鍔犺浇鎻掍欢")
    for name in dict.fromkeys(changed):
        if name == lm and not mem_ok:
            continue
        api.call("POST", "/plugins/reload", {"plugin_id": name}, timeout=180)
    say("  瀹屾垚")

    say("\n===== 缁撴灉 =====")
    for name, ok in results:
        say(f"  {'鉁? if ok else '鉁?} {name}")
    bad = [n for n, ok in results if not ok]
    if bad:
        say("\n鎵撳弶鐨勫彲浠ユ寜鎻愮ず澶勭悊鍚庯紝鍐嶈繍琛屼竴娆℃湰宸ュ叿锛堝凡缁忚濂界殑浼氳嚜鍔ㄨ烦杩囷級銆?)
    say("\n鍘?QQ 涓婄敤澶у彿缁欏ス鍙戜竴鍙ャ€屽湪鍚椼€嶈瘯璇曘€備箣鍓嶈亰杩囩殑璇濓紝鍏堝彂 /reset 娓呮帀鏃у璇濓紝鏂颁汉鏍兼墠浼氱敓鏁堛€?)


def meme_payload(r, key):
    """meme_manager 鐨勬帴鍙ｆ湁鏃剁洿鎺ヨ繑鍥炲瓧娈碉紝鏈夋椂鍖呭湪 data 閲屻€?""
    if key in r:
        return r[key]
    data = r.get("data")
    return data.get(key) if isinstance(data, dict) else None


def meme_pack_ids(api, ext):
    packs = meme_payload(api.call("GET", f"{ext}/packs"), "packs") or []
    return {str(p.get("pack_id") or p.get("id")) for p in packs if isinstance(p, dict)}


def meme_accelerator(api, url=None):
    """涓嶇粰 url锛氳琛ㄦ儏鍖呮彃浠剁幇鍦ㄧ殑 GitHub 鍔犻€熷湴鍧€锛堣涓嶅埌杩斿洖 None锛夈€傜粰 url锛氭敼鎴愬畠锛屾垚鍔熻繑鍥?url锛屽け璐ヨ繑鍥?None銆?""
    r = api.call("GET", "/plugins/config?plugin_id=meme_manager")
    conf = (r.get("data") or {}).get("config") if isinstance(r.get("data"), dict) else None
    if not isinstance(conf, dict):
        return None
    if url is None:
        return str(get_path(conf, "community.github_accelerator_url") or "")
    set_path(conf, "community.github_accelerator_url", url)
    return url if api.ok(api.call("PUT", "/plugins/config", {"plugin_id": "meme_manager", "config": conf})) else None


def meme_use_together(api, ext, wanted):
    """鎶?meme_manager 鐨?default 閫夋嫨瑙勫垯璁炬垚 wanted 杩欏嚑濂椾竴璧风敤锛堝凡缁忔槸浜嗗氨涓嶅姩锛夈€?""
    have = meme_pack_ids(api, ext)
    ids = [p for p in wanted if p in have]
    missing = [p for p in wanted if p not in have]
    if missing:
        warn(f"杩欏嚑濂楄〃鎯呭寘娌¤涓婏紝鍏堜笉绠楄繘鍘伙細{'銆?.join(missing)}")
    if not ids:
        return False
    r = api.call("GET", f"{ext}/settings/rules")
    rules = [x for x in (meme_payload(r, "rules") or []) if isinstance(x, dict)]
    if not api.ok(r):
        warn(f"璇讳笉鍒拌〃鎯呭寘瑙勫垯锛歿api.msg(r)}")
        return False
    cur = next((x for x in reversed(rules) if x.get("scope") == "default"), {})
    cur_ids = cur.get("pack_ids") or ([cur["pack_id"]] if cur.get("pack_id") else [])
    if cur_ids == ids:
        say(f"  榛樿宸茬粡鏄繖 {len(ids)} 濂楋細{'銆?.join(ids)}")
        return True
    keep = [x for x in rules if x.get("scope") != "default"]
    rule = {"id": cur.get("id") or "default", "scope": "default", "pack_id": ids[0], "pack_ids": ids}
    r = api.call("POST", f"{ext}/settings/rules", {"rules": keep + [rule]})
    if not api.ok(r):
        warn(f"琛ㄦ儏鍖呰鍒欐病鏀规垚锛歿api.msg(r)}")
        return False
    say(f"  榛樿鏀规垚鐢ㄨ繖 {len(ids)} 濂楋細{'銆?.join(ids)}")
    return True


def ollama_ready(model):
    def tags():
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
                return [m.get("name", "") for m in json.load(r).get("models", [])]
        except Exception:
            return None
    names = tags()
    if names is None:
        warn("杩炰笉涓婃湰鏈?Ollama锛?27.0.0.1:11434锛夈€傚厛瑁?Ollama 骞舵墦寮€瀹冦€?)
        return False
    if any(n.split(":")[0] == model for n in names):
        say(f"  Ollama 閲屽凡缁忔湁 {model}")
        return True
    exe = shutil.which("ollama") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
    if not os.path.exists(exe) and not shutil.which("ollama"):
        warn("鎵句笉鍒?ollama 鍛戒护銆?)
        return False
    say(f"  姝ｅ湪涓嬭浇鍚戦噺妯″瀷 {model}锛堢害 1.2 GB锛夆€?)
    subprocess.call([exe, "pull", model])
    names = tags() or []
    return any(n.split(":")[0] == model for n in names)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        main()
    except KeyboardInterrupt:
        say("\n宸插彇娑?)
