import urllib.request
from urllib.parse import quote, unquote, urlparse
import re
import os
from datetime import datetime, timedelta, timezone
import opencc

# ===================== 全局核心配置 =====================
ORDERED_CHANNEL_TYPES = [
    "央视", "地方", "体育", "新闻", "电影", "少儿", 
    "音乐", "纪录", "港澳台", "国外", "轮播剧场"
]
REMOVAL_LIST = [
    "「IPV4」", "「IPV6」", "[ipv6]", "[ipv4]", "_电信", "电信", "（HD）", "[超清]","高清", "超清", "-HD", "(HK)", "AKtv", "@", 
    "IPV6", "🎞️", "🎦","[BD]", "[VGA]", "[HD]", "[SD]", "(1080p)", "(720p)", "(480p)", "HD", "｜", "NewTV-", "New_"
]
USER_AGENT = "PostmanRuntime-ApipostRuntime/1.1.0"
URL_FETCH_TIMEOUT = 10
RESPONSE_TIME_THRESHOLD = 2000
TVG_URL = "https://ghfast.top/https://github.com/CCSH/IPTV/raw/refs/heads/main/e.xml.gz"
LOGO_URL_TPL = "https://ghfast.top/https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/logo/{}.png"
SINGLE_CHANNEL_MAX_COUNT = 30

# ===================== 链接域名黑名单 =====================
BLACKLIST_DOMAINS = [
    # freetv系列
    "stream1.freetv.fun",
    "t.freetv.fun",
    "freetv.fun",
    # 失效代理/源
    "ottrrs.hl.chinamobile.com",
    "dd.ddzb.fun",
    "kkk.888.3116598",
    "iptv.catvod.com",
    "satellitepull.cnr.cn",
    # 新增：继续添加失效域名...
]

# ===================== 通用工具函数 =====================
def get_project_dirs() -> dict:
    script_abspath = os.path.abspath(__file__)
    root_dir = os.path.dirname(script_abspath)
    return {
        "root": root_dir,
        "blacklist_auto": os.path.join(root_dir, "assets/whitelist-blacklist/blacklist_auto.txt"),
        "whitelist_respotime": os.path.join(root_dir, "assets/whitelist-blacklist/whitelist_respotime.txt"),
        "blacklist_manual": os.path.join(root_dir, "assets/whitelist-blacklist/blacklist_manual.txt"),
        "whitelist_manual": os.path.join(root_dir, "assets/whitelist-blacklist/whitelist_manual.txt"),
        "corrections_name": os.path.join(root_dir, "assets/corrections_name.txt"),
        "urls": os.path.join(root_dir, "assets/urls.txt"),
        "main_channel": os.path.join(root_dir, "主频道"),
    }

def read_txt(file_path: str, strip: bool = True, skip_empty: bool = True) -> list:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if strip:
                lines = [line.strip() for line in lines]
            if skip_empty:
                lines = [line for line in lines if line]
            return lines
    except FileNotFoundError:
        print(f"[ERROR] 文件未找到: {file_path}")
        return []
    except Exception as e:
        print(f"[ERROR] 读取文件 {file_path} 失败: {str(e)}")
        return []

def write_txt(file_path: str, data: list or str) -> None:
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if isinstance(data, list):
            data = '\n'.join([str(line) for line in data])
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(data)
        print(f"[SUCCESS] 文件写入成功: {os.path.basename(file_path)}")
    except Exception as e:
        print(f"[ERROR] 写入文件 {file_path} 失败: {str(e)}")

def safe_quote_url(url: str) -> str:
    try:
        unquoted = unquote(url)
        return quote(unquoted, safe=':/?&=')
    except Exception:
        return url

def traditional_to_simplified(text: str) -> str:
    if not hasattr(traditional_to_simplified, "converter"):
        traditional_to_simplified.converter = opencc.OpenCC('t2s')
    return traditional_to_simplified.converter.convert(text) if text else ""

def load_blacklist(blacklist_auto_path: str, blacklist_manual_path: str) -> set:
    def _extract_black_urls(file_path):
        lines = read_txt(file_path)
        urls = []
        for line in lines:
            if "," in line:
                url = line.split(',')[1].strip()
                if url:
                    urls.append(url)
        return urls
    return set(_extract_black_urls(blacklist_auto_path) + _extract_black_urls(blacklist_manual_path))

def load_corrections(corrections_path: str) -> dict:
    corrections = {}
    lines = read_txt(corrections_path)
    for line in lines:
        if not line or "," not in line:
            continue
        parts = line.split(',')
        correct_name = parts[0].strip()
        for wrong_name in parts[1:]:
            wrong_name = wrong_name.strip()
            if wrong_name:
                corrections[wrong_name] = correct_name
    print(f"[INFO] 加载频道纠错规则数: {len(corrections)}")
    return corrections

def clean_channel_name(name: str) -> str:
    if not name:
        return ""
    name = name.replace("　", " ")
    name = re.sub(r'[\u200b\u200c\u200d\u200e\u200f]', '', name)
    name = name.replace(" ", "")
    for item in REMOVAL_LIST:
        name = name.replace(item, "")
    name = name.replace("CCTV-", "CCTV")
    name = name.replace("CCTV0", "CCTV")
    name = name.replace("PLUS", "+")
    name = name.replace("iHOT-", "iHOT")
    return name.strip()

def clean_url(url: str) -> str:
    if not url:
        return ""
    dollar_idx = url.rfind('$')
    return url[:dollar_idx].strip() if dollar_idx != -1 else url.strip()

def correct_channel_name(name: str, corrections: dict) -> str:
    if not name or name not in corrections:
        return name
    return corrections[name] if corrections[name] != name else name

def is_blacklisted_domain(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        for black_domain in BLACKLIST_DOMAINS:
            if black_domain in domain:
                print(f"[FILTER] 过滤黑名单域名链接: {domain}")
                return True
    except Exception:
        pass
    return False

def load_channel_dictionaries(main_dir: str, corrections: dict) -> dict:
    channel_types = [
        "央视", "地方", "体育", "新闻", "电影", "少儿", 
        "音乐", "纪录", "港澳台", "国外", "轮播剧场"
    ]
    main_channels = {name: f"{name}.txt" for name in channel_types}
    main_dict = {}
    for chn_type, filename in main_channels.items():
        file_path = os.path.join(main_dir, filename)
        raw_lines = read_txt(file_path)
        clean_lines = []
        for name in raw_lines:
            n = traditional_to_simplified(name)
            n = clean_channel_name(n)
            n = correct_channel_name(n, corrections)
            clean_lines.append(n)
        main_dict[chn_type] = clean_lines
        print(f"[INFO] 加载分类 {chn_type}: {len(raw_lines)} 个频道")
    return main_dict

class ChannelClassifier:
    def __init__(self, main_dict: dict, blacklist: set):
        self.main_dict = main_dict
        self.blacklist = blacklist
        self.channel_data = {}
        self.other_lines = []
        self.other_urls = set()
        self.all_urls = {}
        self.single_chn_count = {}
        for chn_type in main_dict.keys():
            self.channel_data[chn_type] = []
            self.all_urls[chn_type] = set()

    def check_url_exist(self, chn_type: str, url: str) -> bool:
        return url in self.all_urls.get(chn_type, set()) or "127.0.0.1" in url

    def is_single_chn_limit(self, channel_name: str) -> bool:
        if SINGLE_CHANNEL_MAX_COUNT == -1:
            return False
        return self.single_chn_count.get(channel_name, 0) >= SINGLE_CHANNEL_MAX_COUNT

    def add_channel_line(self, chn_type: str, line: str, url: str):
        self.channel_data[chn_type].append(line)
        self.all_urls[chn_type].add(url)
        channel_name = line.split(',')[0].strip()
        self.single_chn_count[channel_name] = self.single_chn_count.get(channel_name, 0) + 1

    def add_other_line(self, line: str, url: str):
        if url not in self.other_urls and url not in self.blacklist:
            self.other_urls.add(url)
            self.other_lines.append(line)

    def classify(self, channel_name: str, channel_url: str, line: str):
        if channel_url in self.blacklist or not channel_url or self.is_single_chn_limit(channel_name):
            return
        for chn_type, chn_names in self.main_dict.items():
            if channel_name in chn_names and not self.check_url_exist(chn_type, channel_url):
                self.add_channel_line(chn_type, line, channel_url)
                return
        self.add_other_line(line, channel_url)

    def get_channel_data(self, chn_type: str) -> list:
        return self.channel_data.get(chn_type, [])

    def get_all_other(self) -> list:
        return self.other_lines

def is_m3u_content(text: str) -> bool:
    if not text:
        return False
    return text.strip().splitlines()[0].strip().startswith("#EXTM3U")

def convert_m3u_to_txt(m3u_content: str) -> list:
    lines = [line.strip() for line in m3u_content.split('\n') if line.strip()]
    txt_lines, channel_name = [], ""
    for line in lines:
        if line.startswith("#EXTM3U"):
            continue
        elif line.startswith("#EXTINF"):
            channel_name = line.split(',')[-1].strip()
        elif line.startswith(("http", "rtmp", "p3p")):
            if channel_name:
                txt_lines.append(f"{channel_name},{line}")
        elif "#genre#" not in line and "," in line and "://" in line:
            if re.match(r'^[^,]+,[^\s]+://[^\s]+$', line):
                txt_lines.append(line)
    return txt_lines

def process_remote_url(url: str, classifier: ChannelClassifier, corrections: dict):
    classifier.other_lines.append(f"{url},#genre#")
    try:
        headers = {'User-Agent': USER_AGENT}
        req = urllib.request.Request(safe_quote_url(url), headers=headers)
        with urllib.request.urlopen(req, timeout=URL_FETCH_TIMEOUT) as resp:
            data = resp.read()
            text = None
            for encoding in ['utf-8', 'gbk', 'gb2312', 'iso-8859-1']:
                try:
                    text = data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if not text:
                return
            if is_m3u_content(text):
                lines = convert_m3u_to_txt(text)
            else:
                lines = [line.strip() for line in text.split('\n') if line.strip()]
        print(f"[PROCESS] 远程源 {url} 提取有效行: {len(lines)}")
        for line in lines:
            process_single_line(line, classifier, corrections)
        classifier.other_lines.append('\n')
    except Exception as e:
        print(f"[ERROR] 处理远程源 {url} 失败: {str(e)}")

def process_single_line(line: str, classifier: ChannelClassifier, corrections: dict):
    if "#genre#" in line or "#EXTINF:" in line or "," not in line or "://" not in line:
        return
    try:
        channel_name, channel_address = line.split(',', 1)
    except ValueError:
        return
    if is_blacklisted_domain(channel_address):
        return
    channel_name = traditional_to_simplified(channel_name)
    channel_name = clean_channel_name(channel_name)
    channel_name = correct_channel_name(channel_name, corrections)
    channel_address = clean_url(channel_address)
    classifier.classify(channel_name, channel_address, f"{channel_name},{channel_address}")

def sort_channel_data(channel_data: list, cfg_list: list) -> list:
    if not channel_data:
        return channel_data
    cfg_index_map = {cfg_name: idx for idx, cfg_name in enumerate(cfg_list)}
    return sorted(channel_data, key=lambda l: cfg_index_map.get(l.split(',')[0] if ',' in l else "", len(cfg_list)))

def generate_live_text(classifier: ChannelClassifier, main_dict: dict) -> tuple:
    bj_time = datetime.now(timezone.utc) + timedelta(hours=8)
    formatted_time = bj_time.strftime("%Y%m%d %H:%M")
    version = f"{formatted_time},http://ottrrs.hl.chinamobile.com/PLTV/88888888/224/3221226537/index.m3u8"
    header = ["更新时间,#genre#", version, '\n']

    lite_lines = header.copy()
    for chn_type in ["央视", "地方", "体育", "新闻", "电影", "港澳台"]:
        chn_data = classifier.get_channel_data(chn_type)
        lite_lines += [f"{chn_type},#genre#"] + sort_channel_data(chn_data, main_dict.get(chn_type, [])) + ['\n']
    lite_lines = lite_lines[:-1] if lite_lines and lite_lines[-1] == '\n' else lite_lines

    full_lines = lite_lines.copy() + ['\n']
    for chn_type in ["少儿", "音乐", "纪录", "国外", "轮播剧场"]:
        chn_data = classifier.get_channel_data(chn_type)
        full_lines += [f"{chn_type},#genre#"] + sort_channel_data(chn_data, main_dict.get(chn_type, [])) + ['\n']
    full_lines = full_lines[:-1] if full_lines and full_lines[-1] == '\n' else full_lines

    return full_lines, lite_lines

def make_m3u(txt_file: str, m3u_file: str, tvg_url: str, logo_tpl: str):
    try:
        if not os.path.exists(txt_file):
            return
        m3u_content = f"#EXTM3U x-tvg-url=\"{tvg_url}\"\n"
        lines = read_txt(txt_file, strip=True, skip_empty=True)
        group_name = ""
        for line in lines:
            if "," not in line:
                continue
            parts = line.split(',', 1)
            if len(parts) != 2:
                continue
            if "#genre#" in parts[1]:
                group_name = parts[0].strip()
                continue
            channel_name, channel_url = parts[0].strip(), parts[1].strip()
            if not channel_url or "://" not in channel_url:
                continue
            logo_url = logo_tpl.format(channel_name)
            m3u_content += (
                f"#EXTINF:-1  tvg-name=\"{channel_name}\" tvg-logo=\"{logo_url}\"  group-title=\"{group_name}\",{channel_name}\n"
                f"{channel_url}\n"
            )
        write_txt(m3u_file, m3u_content)
    except Exception as e:
        print(f"[ERROR] 生成M3U失败 {m3u_file}: {str(e)}")

# ===================== 主函数 =====================
if __name__ == "__main__":
    timestart = datetime.now()
    print(f"[START] 程序开始执行: {timestart.strftime('%Y%m%d %H:%M:%S')}")
    print(f"[INFO] 域名黑名单已启用 ({len(BLACKLIST_DOMAINS)}个): {BLACKLIST_DOMAINS}")
    dirs = get_project_dirs()
    
    blacklist = load_blacklist(dirs["blacklist_auto"], dirs["blacklist_manual"])
    corrections = load_corrections(dirs["corrections_name"])
    main_dict = load_channel_dictionaries(dirs["main_channel"], corrections)
    classifier = ChannelClassifier(main_dict, blacklist)

    print(f"[PROCESS] 处理手动白名单")
    for line in read_txt(dirs["whitelist_manual"]):
        process_single_line(line, classifier, corrections)

    print(f"[PROCESS] 处理自动白名单")
    for line in read_txt(dirs["whitelist_respotime"]):
        if "#genre#" in line or "," not in line or "://" not in line:
            continue
        parts = line.split(",")
        try:
            if float(parts[0].replace('ms', '').strip()) < RESPONSE_TIME_THRESHOLD:
                process_single_line(",".join(parts[1:]), classifier, corrections)
        except (ValueError, IndexError, AttributeError):
            pass

    print(f"[PROCESS] 处理远程URL源")
    for url in read_txt(dirs["urls"]):
        if url.startswith("http"):
            process_remote_url(url, classifier, corrections)

    live_full, live_lite = generate_live_text(classifier, main_dict)
    write_txt(os.path.join(dirs["root"], "live.txt"), live_full)
    write_txt(os.path.join(dirs["root"], "live_lite.txt"), live_lite)
    write_txt(os.path.join(dirs["root"], "others.txt"), classifier.other_lines)

    make_m3u(os.path.join(dirs["root"], "live.txt"), os.path.join(dirs["root"], "live.m3u"), TVG_URL, LOGO_URL_TPL)
    make_m3u(os.path.join(dirs["root"], "live_lite.txt"), os.path.join(dirs["root"], "live_lite.m3u"), TVG_URL, LOGO_URL_TPL)

    elapsed = (datetime.now() - timestart).total_seconds()
    print(f"[END] 执行时间: {int(elapsed // 60)} 分 {int(elapsed % 60)} 秒")
    print(f"[STAT] live.txt行数: {len(live_full)}")
    print(f"[STAT] others.txt行数: {len(classifier.other_lines)}")
