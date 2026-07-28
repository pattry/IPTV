import urllib.request
from urllib.parse import quote, unquote
import re
import os
from datetime import datetime, timedelta, timezone
import opencc

# ===================== 全局核心配置 =====================
# 指定按TXT文件内顺序排列的分类，其余自动字典序排序，按需增删
ORDERED_CHANNEL_TYPES = ["央视频道", "卫视频道", "港澳台", "电影", "电视剧", "埋堆堆", "咪咕直播"]
# 频道名称清理字符集（仅用于clean_channel_name的初步清洗）
REMOVAL_LIST = [
    "「IPV4」", "「IPV6」", "[ipv6]", "[ipv4]", "_电信", "电信", "（HD）", "[超清]","高清", "超清", "-HD", "(HK)", "AKtv", "@", 
    "IPV6", "🎞️", "🎦","[BD]", "[VGA]", "[HD]", "[SD]", "(1080p)", "(720p)", "(480p)", "HD", "｜", "NewTV-", "New_"
]
# 网络请求配置
USER_AGENT = "okhttp/3.15.0"
URL_FETCH_TIMEOUT = 15
# 白名单测速阈值(ms)
RESPONSE_TIME_THRESHOLD = 2000
# M3U相关配置
TVG_URL = "https://ghfast.top/https://github.com/CCSH/IPTV/raw/refs/heads/main/e.xml.gz"
LOGO_URL_TPL = "https://ghfast.top/https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/logo/{}.png"
# 所有单个频道最多保留的有效源数量，可直接修改数字（-1=无限制）
SINGLE_CHANNEL_MAX_COUNT = 18

# ===================== 标准化策略配置 =====================
# 需要去掉HD/画质标记的分类（HD版和非HD版合并）
REMOVE_HD_TYPES = ["央视频道", "卫视频道"]

# 匹不上也保留原名的分类（策略C：尽量匹配，匹不上保留原名）
KEEP_UNMATCHED_TYPES = ["电影", "纪录片", "国际台", "儿童频道"]

# ===================== 港澳台别名映射表 =====================
ALIAS_MAP = {
    # TVB系列
    "翡翠台": "TVB翡翠台",
    "明珠台": "TVBPearl",
    "无线新闻": "TVB互动新闻台",
    "无线新闻台": "TVB互动新闻台",
    "TVBJ2": "TVBJ2",
    
    # 中天系列
    "中天新闻": "中天新闻台",
    
    # 中视系列
    "中视新闻": "中视新闻台",
    
    # 民视系列
    "民视新闻": "民视新闻台",
    
    # 台视系列
    "台视新闻": "台视新闻台",
    
    # 华视系列
    "华视新闻": "华视新闻台",
    
    # 三立系列
    "三立新闻": "三立新闻台",
    
    # 东森系列
    "东森新闻": "东森新闻台",
    
    # 纬来系列（无"台"→有"台"）
    "纬来体育": "纬来体育台",
    "纬来戏剧": "纬来戏剧台",
    "纬来日本": "纬来日本台",
    "纬来电影": "纬来电影台",
    "纬来精彩": "纬来精彩台",
    "纬来综合": "纬来综合台",
    "纬来育乐": "纬来育乐台",
    "纬来音乐": "纬来音乐台",
    
    # 靖天系列
    "靖天戏剧": "靖天戏剧台",
    "靖天日本": "靖天日本台",
    "靖天映画": "靖天映画台",
    "靖天欢乐": "靖天欢乐台",
    "靖天电影": "靖天电影台",
    "靖天综合": "靖天综合台",
    "靖天育乐": "靖天育乐台",
    "靖天资讯": "靖天资讯台",
    "靖天卡通": "靖天卡通台",
    
    # 靖洋系列
    "靖洋戏剧": "靖洋戏剧台",
    "靖洋卡通": "靖洋卡通台",
    
    # 龙华系列
    "龙华偶像": "龙华偶像台",
    "龙华动画": "龙华动画台",
    "龙华影剧": "龙华影剧台",
    "龙华戏剧": "龙华戏剧台",
    "龙华洋片": "龙华洋片台",
    "龙华电影": "龙华电影台",
    "龙华经典": "龙华经典台",
    
    # 壹电视系列
    "壹电视新闻": "壹电视新闻台",
    "壹电视电影": "壹电视电影台",
    "壹电视综合": "壹电视综合台",
    
    # 八大系列
    "八大优": "八大优频道",
    "八大娱乐": "八大娱乐台",
    "八大戏剧": "八大戏剧台",
    "八大第一": "八大第一台",
    "八大精彩": "八大精彩台",
    "八大综合": "八大综合台",
    "八大综艺": "八大综艺台",
    
    # Now系列
    "Now新闻": "Now新闻台",
    "Now直播": "Now直播台",
    "Now财经": "Now财经台",
    "Now华剧": "Now华剧台",
    "Now报价": "Now报价台",
    "Now爆谷星影": "Now爆谷星影台",
}

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
        "local_channel": os.path.join(root_dir, "地方台")
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

# ===================== 黑名单/纠错字典处理 =====================
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
    auto_urls = _extract_black_urls(blacklist_auto_path)
    manual_urls = _extract_black_urls(blacklist_manual_path)
    combined = set(auto_urls + manual_urls)
    print(f"[INFO] 合并黑名单URL数: {len(combined)}")
    return combined

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

# ===================== 频道名称/URL处理 =====================
def clean_channel_name(name: str) -> str:
    """初步清洗频道名，删除无关标记"""
    if not name:
        return ""
        
    # 全角空格转半角
    name = name.replace("　", " ")
    # 删除复制粘贴带来的零宽隐形空白
    name = re.sub(r'[\u200b\u200c\u200d\u200e\u200f]', '', name)
    # 删除所有半角空格
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

# ===================== 新增：分类型频道名标准化 =====================
def normalize_channel_name(name: str, chn_type: str = None) -> str:
    """
    根据分类类型，智能标准化频道名用于字典匹配。
    
    Args:
        name: 清洗后的频道名
        chn_type: 所属分类（用于判断是否去掉HD标记）
    
    Returns:
        标准化后的纯小写字母数字标识符
    """
    if not name:
        return ""
    
    # 1. 基础清洗
    name = name.replace("　", " ")
    name = re.sub(r'[\u200b\u200c\u200d\u200e\u200f]', '', name)
    name = name.strip()
    name = name.lower()
    
    # 2. 中国教育台
    name = re.sub(r'中国教育\s*一?\s*套?', 'cetv1', name)
    name = re.sub(r'中国教育\s*(\d)\s*台?', r'cetv\1', name)
    name = re.sub(r'cetv[-\s]*(\d)', r'cetv\1', name)
    
    # 3. CCTV5+ 必须最先处理（避免被后续规则破坏）
    name = re.sub(r'cctv[-\s]*5\s*[+＋]', 'cctv5+', name)
    name = re.sub(r'cctv\s*5\s*plus', 'cctv5+', name)
    
    # 4. CCTV4K / CCTV8K
    name = re.sub(r'cctv[-\s]*4\s*k', 'cctv4k', name)
    name = re.sub(r'cctv[-\s]*8\s*k', 'cctv8k', name)
    
    # 5. CCTV1-CCTV17
    name = re.sub(r'cctv[-\s]*(\d+)', r'cctv\1', name)
    
    # 6. 去掉画质标记（根据分类决定）
    if chn_type in REMOVE_HD_TYPES:
        hd_tags = ['hd', 'fhd', 'uhd', 'sd', '高清', '标清', '超清', '蓝光', '普清']
        for tag in hd_tags:
            name = name.replace(tag, '')
    
    # 7. 去掉所有修饰词
    modifiers = [
        '综合', '财经', '综艺', '体育', '电影', '电视剧', '科教', '戏曲',
        '社会与法', '法制', '新闻', '少儿', '音乐', '纪录', '纪录片',
        '国防军事', '农业农村', '国际', '中文国际', '奥林匹克',
        '娱乐', '精品', '电视指南', '卫生健康', '文化精品',
        '亚洲', '欧洲', '美洲', '港澳版', '海外版', '国际版',
        '一套', '二套', '三套', '四套', '五套', '六套', '七套', '八套',
        'h265', 'hevc', 'avs2', 'avs3',
        'ipv4', 'ipv6', 'asi', 'eu', 'us', 'euo', 'ame',
        '(亚洲)', '(欧洲)', '(美洲)', '(港澳版)', '(国际版)', '(海外版)',
        '(hd)', '(sd)', '(4k)', '(8k)',
        '（hd）', '（sd）', '（4k）', '（8k）',
        '「ipv4」', '「ipv6」', '[ipv6]', '[ipv4]',
        '｜', '@', '🎞️', '🎦', '[bd]', '[vga]', '[hd]', '[sd]',
        '(1080p)', '(720p)', '(480p)',
        'newtv-', 'new_', '_电信', '电信', 'aktv',
    ]
    for mod in modifiers:
        name = name.replace(mod, '')
    
    # 8. 删除空格和所有剩余特殊字符（保留字母、数字、+）
    name = name.replace(' ', '')
    name = re.sub(r'[^a-z0-9+]', '', name)
    
    return name.strip()

# ===================== 频道字典加载 =====================
def load_channel_dictionaries(main_dir: str, local_dir: str) -> tuple:
    """
    返回两个元组：
    (main_normalized, main_display), (local_normalized, local_display)
    """
    # 主频道数组
    main_name_list = [
        "央视频道", "卫视频道", "体育频道", "电影", "电视剧", "港澳台",
        "国际台", "纪录片", "戏曲频道", "解说频道", "春晚", "NewTV",
        "iHOT", "儿童频道", "综艺频道", "埋堆堆", "音乐频道", "游戏频道",
        "收音机频道", "直播中国", "MTV", "咪咕直播"
    ]
    main_channels = {name: f"{name}.txt" for name in main_name_list}

    # 地方台数组
    local_name_list = [
        "上海频道", "浙江频道", "江苏频道", "广东频道", "湖南频道", "安徽频道",
        "海南频道", "内蒙频道", "湖北频道", "辽宁频道", "陕西频道", "山西频道",
        "山东频道", "云南频道", "北京频道", "重庆频道", "福建频道", "甘肃频道",
        "广西频道", "贵州频道", "河北频道", "河南频道", "黑龙江频道", "吉林频道",
        "江西频道", "宁夏频道", "青海频道", "四川频道", "天津频道", "新疆频道"
    ]
    local_channels = {name: f"{name}.txt" for name in local_name_list}

    # 两个字典：一个存标准化名（匹配用），一个存原始名（输出用）
    main_normalized = {}
    main_display = {}
    
    for chn_type, filename in main_channels.items():
        file_path = os.path.join(main_dir, filename)
        raw_lines = read_txt(file_path)
        
        display_names = []
        normalized_names = []
        for name in raw_lines:
            n = traditional_to_simplified(name)
            n = clean_channel_name(n)
            display_names.append(n)
            # 用该分类的策略标准化
            normalized_names.append(normalize_channel_name(n, chn_type))
        
        main_normalized[chn_type] = normalized_names
        main_display[chn_type] = display_names
        print(f"[INFO] 加载主频道 {chn_type}: {len(raw_lines)} 个")

    local_normalized = {}
    local_display = {}
    
    for chn_type, filename in local_channels.items():
        file_path = os.path.join(local_dir, filename)
        raw_lines = read_txt(file_path)
        
        display_names = []
        normalized_names = []
        for name in raw_lines:
            n = traditional_to_simplified(name)
            n = clean_channel_name(n)
            display_names.append(n)
            # 地方台保留HD标记
            normalized_names.append(normalize_channel_name(n, chn_type))
        
        local_normalized[chn_type] = normalized_names
        local_display[chn_type] = display_names
        print(f"[INFO] 加载地方台 {chn_type}: {len(raw_lines)} 个")

    return (main_normalized, main_display), (local_normalized, local_display)

# ===================== 频道分类核心 =====================
class ChannelClassifier:
    def __init__(self, main_dicts: tuple, local_dicts: tuple, blacklist: set):
        self.main_normalized, self.main_display = main_dicts
        self.local_normalized, self.local_display = local_dicts
        self.blacklist = blacklist
        self.channel_data = {}
        self.other_lines = []
        self.other_urls = set()
        self.all_urls = {}
        self.single_chn_count = {}
        
        # 初始化分类数据
        all_types = list(self.main_normalized.keys()) + list(self.local_normalized.keys())
        for chn_type in all_types:
            self.channel_data[chn_type] = []
            self.all_urls[chn_type] = set()

    def check_url_exist(self, chn_type: str, url: str) -> bool:
        if url in self.all_urls.get(chn_type, set()) or "127.0.0.1" in url:
            return True
        return False

    def is_single_chn_limit(self, channel_name: str) -> bool:
        if SINGLE_CHANNEL_MAX_COUNT == -1:
            return False
        current_count = self.single_chn_count.get(channel_name, 0)
        if current_count >= SINGLE_CHANNEL_MAX_COUNT:
            return True
        return False

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
        """
        智能分类方法。
        1. 先查别名映射
        2. 再尝试匹配主频道字典
        3. 再尝试匹配地方台字典
        4. 未匹配：策略C的分类保留原名，其余扔others
        """
        if channel_url in self.blacklist or not channel_url or self.is_single_chn_limit(channel_name):
            return
        
        # 1. 先查别名映射
        resolved_name = ALIAS_MAP.get(channel_name, channel_name)
        
        # 2. 尝试在主频道字典中匹配
        for chn_type, normalized_list in self.main_normalized.items():
            normalized_input = normalize_channel_name(resolved_name, chn_type)
            if normalized_input in normalized_list:
                if not self.check_url_exist(chn_type, channel_url):
                    idx = normalized_list.index(normalized_input)
                    display_name = self.main_display[chn_type][idx]
                    new_line = f"{display_name},{channel_url}"
                    self.add_channel_line(chn_type, new_line, channel_url)
                return
        
        # 3. 尝试在地方台字典中匹配
        for chn_type, normalized_list in self.local_normalized.items():
            normalized_input = normalize_channel_name(resolved_name, chn_type)
            if normalized_input in normalized_list:
                if not self.check_url_exist(chn_type, channel_url):
                    idx = normalized_list.index(normalized_input)
                    display_name = self.local_display[chn_type][idx]
                    new_line = f"{display_name},{channel_url}"
                    self.add_channel_line(chn_type, new_line, channel_url)
                return
        
        # 4. 未匹配：根据策略决定去向
        # 策略C：尝试在KEEP_UNMATCHED_TYPES中保留原名
        for chn_type in KEEP_UNMATCHED_TYPES:
            if chn_type in self.channel_data:
                normalized_input = normalize_channel_name(channel_name, chn_type)
                # 如果匹配上该分类的字典，放入该分类
                if chn_type in self.main_normalized and normalized_input in self.main_normalized[chn_type]:
                    if not self.check_url_exist(chn_type, channel_url):
                        idx = self.main_normalized[chn_type].index(normalized_input)
                        display_name = self.main_display[chn_type][idx]
                        new_line = f"{display_name},{channel_url}"
                        self.add_channel_line(chn_type, new_line, channel_url)
                    return
        
        # 默认：扔到 others
        self.add_other_line(line, channel_url)

    def get_channel_data(self, chn_type: str) -> list:
        return self.channel_data.get(chn_type, [])

    def get_all_other(self) -> list:
        return self.other_lines

# ===================== 数据处理与生成 =====================
def is_m3u_content(text: str) -> bool:
    if not text:
        return False
    first_line = text.strip().splitlines()[0].strip()
    return first_line.startswith("#EXTM3U")

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
            for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'iso-8859-1']:
                try:
                    text = data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if not text:
                print(f"[ERROR] 远程源 {url} 解码失败")
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
    
    # 频道名标准化（简繁转换→清洗→纠错）
    channel_name = traditional_to_simplified(channel_name)
    channel_name = clean_channel_name(channel_name)
    channel_name = correct_channel_name(channel_name, corrections)
    channel_address = clean_url(channel_address)
    
    new_line = f"{channel_name},{channel_address}"
    # 传入标准化后的频道名做分类
    classifier.classify(channel_name, channel_address, new_line)

def sort_channel_data(channel_data: list, chn_type: str, cfg_list: list) -> list:
    if not channel_data:
        return channel_data
    
    if chn_type in ORDERED_CHANNEL_TYPES:
        cfg_index_map = {cfg_name: idx for idx, cfg_name in enumerate(cfg_list)}
        def _ordered_key(line):
            name = line.split(',')[0] if ',' in line else ""
            return cfg_index_map.get(name, len(cfg_list))
        return sorted(channel_data, key=_ordered_key)
    else:
        def _dict_key(line):
            name = line.split(',')[0] if ',' in line else ""
            pure_name = re.sub(r'[^\w\u4e00-\u9fff]', '', name)
            return pure_name if pure_name else name
        return sorted(channel_data, key=_dict_key)

def generate_live_text(classifier: ChannelClassifier, main_display: dict) -> tuple[list, list]:
    bj_time = datetime.now(timezone.utc) + timedelta(hours=8)
    formatted_time = bj_time.strftime("%Y%m%d %H:%M")
    version = f"{formatted_time},http://ottrrs.hl.chinamobile.com/PLTV/88888888/224/3221226537/index.m3u8"
    header = ["更新时间,#genre#", version, '\n']

    # 生成lite精简版
    lite_lines = header.copy()
    lite_sort_types = [
        "央视频道", "卫视频道", "港澳台", "电影", "电视剧", "综艺频道",
        "NewTV", "iHOT", "体育频道", "咪咕直播", "埋堆堆", "音乐频道", "游戏频道", "解说频道"
    ]
    for chn_type in lite_sort_types:
        chn_data = classifier.get_channel_data(chn_type)
        sort_list = main_display.get(chn_type, [])
        sorted_data = sort_channel_data(chn_data, chn_type, sort_list)
        lite_lines += [f"{chn_type},#genre#"] + sorted_data + ['\n']
    lite_lines = lite_lines[:-1] if lite_lines and lite_lines[-1] == '\n' else lite_lines

    # 补全剩余生成full版
    full_lines = lite_lines.copy() + ['\n']
    full_other_types = [
        "儿童频道", "国际台", "纪录片", "戏曲频道", "上海频道", "湖南频道",
        "湖北频道", "广东频道", "浙江频道", "山东频道", "江苏频道", "安徽频道",
        "海南频道", "内蒙频道", "辽宁频道", "陕西频道", "山西频道", "云南频道",
        "北京频道", "重庆频道", "福建频道", "甘肃频道", "广西频道", "贵州频道",
        "河北频道", "河南频道", "黑龙江频道", "吉林频道", "江西频道", "宁夏频道",
        "青海频道", "四川频道", "天津频道", "新疆频道", "春晚", "直播中国", "MTV", "收音机频道"
    ]
    for chn_type in full_other_types:
        chn_data = classifier.get_channel_data(chn_type)
        sort_list = main_display.get(chn_type, [])
        sorted_data = sort_channel_data(chn_data, chn_type, sort_list)
        full_lines += [f"{chn_type},#genre#"] + sorted_data + ['\n']
    full_lines = full_lines[:-1] if full_lines and full_lines[-1] == '\n' else full_lines

    return full_lines, lite_lines

def make_m3u(txt_file: str, m3u_file: str, tvg_url: str, logo_tpl: str):
    try:
        if not os.path.exists(txt_file):
            print(f"[ERROR] M3U源文件不存在: {txt_file}")
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
                f"#EXTINF:-1 tvg-name=\"{channel_name}\" tvg-logo=\"{logo_url}\" group-title=\"{group_name}\",{channel_name}\n"
                f"{channel_url}\n"
            )
        write_txt(m3u_file, m3u_content)
    except Exception as e:
        print(f"[ERROR] 生成M3U失败 {m3u_file}: {str(e)}")

# ===================== 主函数执行 =====================
if __name__ == "__main__":
    timestart = datetime.now()
    print(f"[START] 程序开始执行: {timestart.strftime('%Y%m%d %H:%M:%S')}")
    dirs = get_project_dirs()
    
    blacklist = load_blacklist(dirs["blacklist_auto"], dirs["blacklist_manual"])
    corrections = load_corrections(dirs["corrections_name"])
    main_dicts, local_dicts = load_channel_dictionaries(dirs["main_channel"], dirs["local_channel"])
    classifier = ChannelClassifier(main_dicts, local_dicts, blacklist)

    print(f"[PROCESS] 处理手动白名单")
    whitelist_manual = read_txt(dirs["whitelist_manual"])
    classifier.other_lines.append("白名单,#genre#")
    for line in whitelist_manual:
        process_single_line(line, classifier, corrections)

    print(f"[PROCESS] 处理自动白名单（响应时间<{RESPONSE_TIME_THRESHOLD}ms）")
    whitelist_respotime = read_txt(dirs["whitelist_respotime"])
    classifier.other_lines.append("白名单测速,#genre#")
    for line in whitelist_respotime:
        if "#genre#" in line or "," not in line or "://" not in line:
            continue
        parts = line.split(",")
        try:
            time_str = parts[0].replace('ms', '').strip()
            resp_time = float(time_str) if time_str else float('inf')
        except (ValueError, IndexError, AttributeError):
            resp_time = float('inf')
            
        if resp_time < RESPONSE_TIME_THRESHOLD:
            process_single_line(",".join(parts[1:]), classifier, corrections)

    print(f"[PROCESS] 处理远程URL源")
    urls = read_txt(dirs["urls"])
    for url in urls:
        if url.startswith("http"):
            process_remote_url(url, classifier, corrections)

    # 获取 main_display 用于排序
    _, main_display = main_dicts
    live_full, live_lite = generate_live_text(classifier, main_display)
    live_full_path = os.path.join(dirs["root"], "live.txt")
    live_lite_path = os.path.join(dirs["root"], "live_lite.txt")
    others_path = os.path.join(dirs["root"], "others.txt")
    write_txt(live_full_path, live_full)
    write_txt(live_lite_path, live_lite)
    write_txt(others_path, classifier.other_lines)

    print(f"[GENERATE] 生成M3U文件")
    make_m3u(live_full_path, os.path.join(dirs["root"], "live.m3u"), TVG_URL, LOGO_URL_TPL)
    make_m3u(live_lite_path, os.path.join(dirs["root"], "live_lite.m3u"), TVG_URL, LOGO_URL_TPL)

    timeend = datetime.now()
    elapsed = timeend - timestart
    minutes, seconds = int(elapsed.total_seconds() // 60), int(elapsed.total_seconds() % 60)
    blacklist_count = len(blacklist)
    live_count = len(live_full)
    others_count = len(classifier.other_lines)
    
    print("=" * 60)
    print(f"[END] 程序执行完成: {timeend.strftime('%Y%m%d %H:%M:%S')}")
    print(f"[STAT] 执行时间: {minutes} 分 {seconds} 秒")
    print(f"[STAT] live.txt行数: {live_count}")
    print(f"[STAT] others.txt行数: {others_count}")
    print("=" * 60)
