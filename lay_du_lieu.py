# -*- coding: utf-8 -*-
"""
LẤY DỮ LIỆU BÁN CHẠY SHOPEE – CHẠY MỖI ĐÊM LÚC 0 GIỜ 13

Cách hoạt động:
1. Với từng nhóm hàng trong nhom_hang.json, lấy các sản phẩm bán chạy nhất theo từng từ khóa,
   qua cổng dữ liệu chính thức của chương trình Tiếp thị liên kết Shopee (Shopee Affiliate).
2. RỔ SẢN PHẨM: sản phẩm nào đã từng lọt top thì được theo dõi tiếp 30 ngày, kể cả khi rớt khỏi top.
   Nhờ vậy số bán của nhóm không bị hụt khi một sản phẩm tạm rớt hạng.
3. Shopee chỉ cho biết "tổng số đã bán từ trước tới nay" của mỗi sản phẩm.
   Mỗi đêm chương trình chụp lại con số đó (ảnh chụp mang tên ngày vừa kết thúc), rồi lấy hiệu số:
     Số bán trong ngày  = đã bán hết ngày này − đã bán hết ngày hôm trước
     Số bán 7 ngày qua  = đã bán hết ngày này − đã bán hết ngày cách đó 7 ngày
     Số bán 30 ngày qua = tương tự với 30 ngày
4. Xếp hạng nhóm hàng, so thứ hạng với lần cập nhật trước (mũi tên tăng/tụt), gắn nhãn tín hiệu.
5. SẢN PHẨM BÙNG NỔ: sản phẩm có số bán trong ngày gấp 3 lần trung bình các ngày trước.
6. NÊN QUẢNG BÁ: sản phẩm mang lại hoa hồng ước tính cao nhất trong 7 ngày qua.
7. NGÀY SIÊU SALE (file ngay_khuyen_mai.json): số bán các ngày này cao bất thường,
   nên không dùng để gắn nhãn tín hiệu và không dùng làm mốc so sánh sản phẩm bùng nổ.
8. Ghi ra du_lieu/bang_xep_hang.json cho trang web đọc, và gửi tóm tắt về Telegram.

Các mã bí mật lấy từ biến môi trường (đặt trong mục Secrets của GitHub):
  SHOPEE_APP_ID       : mã ứng dụng tiếp thị liên kết Shopee
  SHOPEE_SECRET       : khóa bí mật (API key) tiếp thị liên kết Shopee
  TELEGRAM_BOT_TOKEN  : mã của con bot Telegram (không có thì bỏ qua bước gửi)
  TELEGRAM_CHAT_ID    : mã cuộc trò chuyện nhận tin (không có thì bỏ qua bước gửi)
"""

import hashlib
import html
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from phan_tich import phan_tich_toan_bo

# ======================= THÔNG SỐ (sửa số ở đây nếu muốn) =======================
SO_SAN_PHAM_MOI_TRANG = 50          # mỗi lần hỏi Shopee lấy 50 sản phẩm
SO_TRANG_MOI_TU_KHOA = 2            # mỗi từ khóa lấy 2 trang = 100 sản phẩm bán chạy nhất
NGHI_GIUA_CAC_LAN_HOI = 1.0         # nghỉ 1 giây giữa hai lần hỏi theo từ khóa
NGHI_KHI_HOI_TUNG_SAN_PHAM = 0.4    # nghỉ 0,4 giây giữa hai lần hỏi lại từng sản phẩm trong rổ

SO_NGAY_THEO_DOI_TRONG_RO = 30      # sản phẩm rớt top vẫn được theo dõi tiếp 30 ngày
SO_SAN_PHAM_HOI_LAI_TOI_DA = 1500   # mỗi đêm hỏi lại tối đa 1.500 sản phẩm trong rổ (tránh bị Shopee chặn)
SO_NGAY_GIU_ANH_CHUP = 70           # giữ ảnh chụp 70 ngày (đủ so tháng này với tháng trước)

SO_SAN_PHAM_HANG_DAU = 30           # số sản phẩm trong bảng "bán nhiều nhất"
SO_SAN_PHAM_MOI_NHOM = 10           # số sản phẩm hiện ra khi bấm vào một nhóm

TOP_DAU = 5                         # nhóm hạng 1–5 là "tốp đầu"
SO_BAC_TANG_DANG_KE = 2             # nhóm từ ngoài tốp đầu tăng từ 2 bậc trở lên → "đang vươn lên"
PHAN_TRAM_GIAM_DANG_KE = 10         # nhóm tốp đầu có số bán giảm từ 10% trở lên → "đang giảm"

BUNG_NO_GAP_LAN = 3                 # bán trong ngày gấp từ 3 lần trung bình các ngày trước → "bùng nổ"
BUNG_NO_SO_BAN_TOI_THIEU = 30       # và phải bán được ít nhất 30 cái trong ngày (bỏ hàng bán lẻ tẻ)
BUNG_NO_SO_NGAY_SO_SANH = 7         # trung bình tính trên tối đa 7 ngày trước đó
BUNG_NO_SO_NGAY_TOI_THIEU = 3       # cần ít nhất 3 ngày trước đó mới xét
SO_SAN_PHAM_BUNG_NO = 20            # hiện 20 sản phẩm bùng nổ mạnh nhất

SO_SAN_PHAM_NEN_QUANG_BA = 20       # hiện 20 sản phẩm hoa hồng cao nhất

# ======================= ĐƯỜNG DẪN =======================
THU_MUC = Path(__file__).resolve().parent
FILE_NHOM_HANG = THU_MUC / "nhom_hang.json"
FILE_NGAY_KHUYEN_MAI = THU_MUC / "ngay_khuyen_mai.json"
THU_MUC_DU_LIEU = THU_MUC / "du_lieu"
THU_MUC_ANH_CHUP = THU_MUC_DU_LIEU / "anh_chup"
FILE_SAN_PHAM = THU_MUC_DU_LIEU / "san_pham.json"
FILE_XEP_HANG = THU_MUC_DU_LIEU / "bang_xep_hang.json"

DIA_CHI_SHOPEE = "https://open-api.affiliate.shopee.vn/graphql"
GIO_VIET_NAM = timezone(timedelta(hours=7))

CAC_KY = [
    {"ma": "ngay", "ten": "Trong ngày", "so_ngay": 1},
    {"ma": "tuan", "ten": "7 ngày qua", "so_ngay": 7},
    {"ma": "thang", "ten": "30 ngày qua", "so_ngay": 30},
]

TRUONG_CO_BAN = ("itemId productName priceMin priceMax sales ratingStar imageUrl "
                 "offerLink productLink shopName productCatIds")
# Các trường có thể Shopee không trả (tùy tài khoản). Trường nào bị Shopee báo lỗi thì tự bỏ, vẫn chạy tiếp.
TRUONG_TUY_CHON = ["commissionRate", "shopId", "shopType"]
truong_bi_bo = set()


# ======================= HỎI DỮ LIỆU SHOPEE =======================
def hoi_shopee(cau_hoi: str) -> dict:
    """Gửi một câu hỏi tới cổng dữ liệu tiếp thị liên kết Shopee, có ký xác thực."""
    ma_ung_dung = os.environ["SHOPEE_APP_ID"]
    khoa_bi_mat = os.environ["SHOPEE_SECRET"]
    noi_dung = json.dumps({"query": cau_hoi}, ensure_ascii=False, separators=(",", ":"))
    moc_gio = str(int(time.time()))
    chu_ky = hashlib.sha256((ma_ung_dung + moc_gio + noi_dung + khoa_bi_mat).encode("utf-8")).hexdigest()
    tieu_de = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={ma_ung_dung}, Timestamp={moc_gio}, Signature={chu_ky}",
    }
    tra_loi = requests.post(DIA_CHI_SHOPEE, data=noi_dung.encode("utf-8"), headers=tieu_de, timeout=30)
    tra_loi.raise_for_status()
    ket_qua = tra_loi.json()
    if ket_qua.get("errors"):
        raise RuntimeError(f"Shopee báo lỗi: {ket_qua['errors']}")
    return ket_qua["data"]


def hoi_danh_sach_san_pham(dieu_kien: str) -> list:
    """Hỏi Shopee danh sách sản phẩm, xin thêm các trường tùy chọn (hoa hồng, mã shop, loại shop).
    Trường nào Shopee không chấp nhận thì bỏ trường đó và hỏi lại."""
    them = [t for t in TRUONG_TUY_CHON if t not in truong_bi_bo]
    truong = TRUONG_CO_BAN + "".join(" " + t for t in them)
    cau_hoi = "{productOfferV2(%s){nodes{%s}pageInfo{page limit hasNextPage}}}" % (dieu_kien, truong)
    try:
        du_lieu = hoi_shopee(cau_hoi)
    except RuntimeError as loi:
        bao_loi = str(loi)
        loi_truong = [t for t in them if t in bao_loi]
        if loi_truong:
            print(f"  Shopee không trả trường {', '.join(loi_truong)}, bỏ trường này và chạy tiếp.")
            truong_bi_bo.update(loi_truong)
            return hoi_danh_sach_san_pham(dieu_kien)
        raise
    return du_lieu["productOfferV2"]["nodes"] or []


def tao_lien_ket_shop(ma_shop: str) -> dict:
    """Lấy link tiếp thị liên kết và ảnh đại diện (logo) thật của gian hàng từ Shopee.
    Cách 1: hỏi danh sách gian hàng tiếp thị liên kết (shopOfferV2) theo mã shop, có sẵn link và logo.
    Cách 2 (dự phòng): tự tạo link rút gọn tới trang gian hàng; khi đó chưa có logo."""
    try:
        du_lieu = hoi_shopee("{shopOfferV2(shopId:%d,page:1,limit:1){nodes{shopId shopName imageUrl offerLink}}}" % int(ma_shop))
        ds = du_lieu["shopOfferV2"]["nodes"] or []
        if ds and ds[0].get("offerLink"):
            return {"lien_ket": ds[0]["offerLink"], "logo": chuan_anh(ds[0].get("imageUrl"))}
    except Exception:
        pass
    dia_chi = f"https://shopee.vn/shop/{int(ma_shop)}"
    du_lieu = hoi_shopee('mutation{generateShortLink(input:{originUrl:"%s",subIds:["radar","gianhang"]}){shortLink}}' % dia_chi)
    return {"lien_ket": du_lieu["generateShortLink"]["shortLink"], "logo": ""}


def lay_theo_tu_khoa(tu_khoa: str, trang: int) -> list:
    """Một trang sản phẩm theo từ khóa, xếp theo số đã bán từ cao xuống thấp (sortType 2)."""
    return hoi_danh_sach_san_pham(
        "keyword:%s,sortType:2,page:%d,limit:%d" % (json.dumps(tu_khoa, ensure_ascii=False), trang, SO_SAN_PHAM_MOI_TRANG))


def lay_theo_ma(ma_san_pham: str) -> dict:
    """Hỏi lại đúng một sản phẩm theo mã (dùng cho sản phẩm trong rổ đã rớt khỏi top)."""
    danh_sach = hoi_danh_sach_san_pham("itemId:%d,page:1,limit:1" % int(ma_san_pham))
    return danh_sach[0] if danh_sach else None


# ======================= ĐỌC / GHI FILE =======================
def doc_json(duong_dan: Path, mac_dinh):
    if duong_dan.exists():
        return json.loads(duong_dan.read_text(encoding="utf-8"))
    return mac_dinh


def ghi_json(duong_dan: Path, du_lieu, gon: bool = False):
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    noi_dung = (json.dumps(du_lieu, ensure_ascii=False, separators=(",", ":")) if gon
                else json.dumps(du_lieu, ensure_ascii=False, indent=1))
    duong_dan.write_text(noi_dung, encoding="utf-8")


def doc_tat_ca_anh_chup() -> dict:
    """Trả về {ngày: {mã sản phẩm: tổng đã bán tính đến hết ngày đó}}."""
    ket_qua = {}
    for file in sorted(THU_MUC_ANH_CHUP.glob("*.json")):
        ket_qua[date.fromisoformat(file.stem)] = doc_json(file, {}).get("da_ban", {})
    return ket_qua


def doc_ngay_khuyen_mai() -> dict:
    """Trả về {ngày: tên đợt sale}."""
    cau_hinh = doc_json(FILE_NGAY_KHUYEN_MAI, {"ngay_sale": []})
    return {date.fromisoformat(m["ngay"]): m["ten"] for m in cau_hinh.get("ngay_sale", [])}


def doi_so(gia_tri) -> float:
    try:
        return float(gia_tri)
    except (TypeError, ValueError):
        return 0.0


def chuan_anh(gia_tri) -> str:
    """Ảnh thật của Shopee. Có lúc Shopee chỉ trả mã ảnh, thì ghép thành đường dẫn đầy đủ trên máy chủ ảnh của Shopee."""
    gia_tri = (gia_tri or "").strip()
    if not gia_tri:
        return ""
    if gia_tri.startswith("//"):
        return "https:" + gia_tri
    if gia_tri.startswith("http"):
        return gia_tri
    return "https://down-vn.img.susercontent.com/file/" + gia_tri


def doi_loai_shop(gia_tri) -> list:
    """Shopee trả loại shop dạng số hoặc danh sách số: 1 = Shopee Mall, 2 = Shop Yêu thích, 4 = Shop Yêu thích+."""
    ds = gia_tri if isinstance(gia_tri, list) else [gia_tri]
    ten = {1: "mall", 2: "yeu_thich", 4: "yeu_thich_plus"}
    return [ten[int(x)] for x in ds if str(x).lstrip("-").isdigit() and int(x) in ten]


def doi_ty_le_hoa_hong(gia_tri):
    """Shopee có thể trả '0.05' (nghĩa là 5%) hoặc '5'. Đưa về dạng phần trăm, ví dụ 5.0."""
    if gia_tri in (None, ""):
        return None
    so = doi_so(gia_tri)
    if so <= 0:
        return None
    return round(so * 100, 2) if so <= 1 else round(so, 2)


# ======================= BƯỚC 1: THU THẬP =======================
def ghi_nhan_san_pham(sp: dict, ten_nhom: str, thong_tin: dict, ngay: date, vao_top: bool, tu_khoa: str = "") -> tuple:
    ma = str(sp["itemId"])
    cu = thong_tin.get(ma, {})
    hoa_hong = doi_ty_le_hoa_hong(sp.get("commissionRate"))
    thong_tin[ma] = {
        "ten": sp.get("productName", "") or cu.get("ten", ""),
        "gia": doi_so(sp.get("priceMin")) or cu.get("gia", 0),
        "danh_gia": doi_so(sp.get("ratingStar")),
        "anh": chuan_anh(sp.get("imageUrl")) or cu.get("anh", ""),   # ảnh thật người bán đăng trên Shopee
        "duong_dan": sp.get("offerLink") or sp.get("productLink") or cu.get("duong_dan", ""),
        "cua_hang": sp.get("shopName", "") or cu.get("cua_hang", ""),
        "ma_shop": str(sp.get("shopId") or cu.get("ma_shop") or ""),
        "loai_shop": doi_loai_shop(sp.get("shopType")) if sp.get("shopType") is not None else cu.get("loai_shop", []),
        # Sản phẩm giữ nhóm được gán lần đầu, tránh nhảy nhóm khi nằm trong nhiều từ khóa
        "nhom": cu.get("nhom", ten_nhom),
        "tu_khoa": cu.get("tu_khoa", tu_khoa),   # loại hàng (từ khóa tìm thấy lần đầu)
        "hoa_hong": hoa_hong if hoa_hong is not None else cu.get("hoa_hong"),
        "lan_cuoi_vao_top": ngay.isoformat() if vao_top else cu.get("lan_cuoi_vao_top", ngay.isoformat()),
        "lan_cuoi_thay": ngay.isoformat(),
    }
    return ma, int(sp.get("sales") or 0)


def thu_thap(ngay: date, ham_theo_tu_khoa=lay_theo_tu_khoa, ham_theo_ma=lay_theo_ma):
    cau_hinh = doc_json(FILE_NHOM_HANG, {"nhom_hang": []})
    thong_tin = doc_json(FILE_SAN_PHAM, {})
    da_ban = {}

    # 1a. Sản phẩm bán chạy theo từng từ khóa
    so_lan_loi = 0
    for nhom in cau_hinh["nhom_hang"]:
        for tu_khoa in nhom["tu_khoa"]:
            for trang in range(1, SO_TRANG_MOI_TU_KHOA + 1):
                try:
                    danh_sach = ham_theo_tu_khoa(tu_khoa, trang)
                except Exception as loi:
                    so_lan_loi += 1
                    print(f"  Lỗi khi lấy '{tu_khoa}' trang {trang}: {loi}")
                    break
                for sp in danh_sach:
                    ma, so = ghi_nhan_san_pham(sp, nhom["ten"], thong_tin, ngay, vao_top=True, tu_khoa=tu_khoa)
                    da_ban[ma] = so
                print(f"  {nhom['ten']} | {tu_khoa} | trang {trang}: {len(danh_sach)} sản phẩm")
                if len(danh_sach) < SO_SAN_PHAM_MOI_TRANG:
                    break
                time.sleep(NGHI_GIUA_CAC_LAN_HOI)

    if not da_ban:
        raise RuntimeError(f"Không lấy được sản phẩm nào (số lần lỗi: {so_lan_loi}). Không ghi ảnh chụp lần này.")
    print(f"Lấy theo từ khóa: {len(da_ban)} sản phẩm.")

    # 1b. Hỏi lại các sản phẩm trong rổ đã rớt khỏi top (vẫn còn trong hạn theo dõi)
    han_theo_doi = (ngay - timedelta(days=SO_NGAY_THEO_DOI_TRONG_RO)).isoformat()
    can_hoi_lai = [m for m, v in thong_tin.items()
                   if m not in da_ban and v.get("lan_cuoi_vao_top", "") >= han_theo_doi]
    can_hoi_lai.sort(key=lambda m: thong_tin[m].get("lan_cuoi_vao_top", ""), reverse=True)
    can_hoi_lai = can_hoi_lai[:SO_SAN_PHAM_HOI_LAI_TOI_DA]
    so_hoi_duoc, loi_lien_tiep = 0, 0
    for ma in can_hoi_lai:
        try:
            sp = ham_theo_ma(ma)
            loi_lien_tiep = 0
        except Exception as loi:
            loi_lien_tiep += 1
            if loi_lien_tiep >= 10:
                print(f"  Hỏi lại theo mã lỗi 10 lần liền ({loi}). Dừng phần hỏi lại rổ sản phẩm.")
                break
            continue
        if sp:
            m, so = ghi_nhan_san_pham(sp, thong_tin.get(ma, {}).get("nhom", ""), thong_tin, ngay, vao_top=False)
            da_ban[m] = so
            so_hoi_duoc += 1
        time.sleep(NGHI_KHI_HOI_TUNG_SAN_PHAM)
    print(f"Hỏi lại rổ sản phẩm: {so_hoi_duoc}/{len(can_hoi_lai)} sản phẩm.")

    # 1c. Dọn dữ liệu cũ, ghi ảnh chụp
    gioi_han = (ngay - timedelta(days=SO_NGAY_GIU_ANH_CHUP)).isoformat()
    thong_tin = {m: v for m, v in thong_tin.items() if v["lan_cuoi_thay"] >= gioi_han}
    ghi_json(THU_MUC_ANH_CHUP / f"{ngay.isoformat()}.json", {"ngay": ngay.isoformat(), "da_ban": da_ban})
    ghi_json(FILE_SAN_PHAM, thong_tin)
    for file in THU_MUC_ANH_CHUP.glob("*.json"):
        if file.stem < gioi_han:
            file.unlink()
    print(f"Đã chụp {len(da_ban)} sản phẩm, tính đến hết ngày {ngay.isoformat()}.")


# ======================= BƯỚC 2: TÍNH XẾP HẠNG =======================
def tim_anh_chup_truoc(cac_ngay: list, moc: date):
    """Ảnh chụp gần nhất vào đúng hoặc trước ngày mốc."""
    phu_hop = [n for n in cac_ngay if n <= moc]
    return max(phu_hop) if phu_hop else None


def so_ban_giua(anh_dau: dict, anh_cuoi: dict) -> dict:
    """Số bán của từng sản phẩm giữa hai lần chụp. Chỉ tính sản phẩm có mặt ở cả hai lần."""
    return {ma: max(0, cuoi - anh_dau[ma]) for ma, cuoi in anh_cuoi.items() if ma in anh_dau}


def mo_ta_san_pham(ma: str, so_ban: int, thong_tin: dict) -> dict:
    tt = thong_tin.get(ma, {})
    gia = tt.get("gia", 0)
    hoa_hong = tt.get("hoa_hong")
    return {
        "ma": ma, "ten": tt.get("ten", ""), "nhom": tt.get("nhom", ""), "loai": tt.get("tu_khoa", ""),
        "gia": gia, "danh_gia": tt.get("danh_gia", 0), "anh": tt.get("anh", ""),
        "duong_dan": tt.get("duong_dan", ""), "cua_hang": tt.get("cua_hang", ""),
        "so_ban": so_ban, "doanh_thu": round(so_ban * gia),
        "hoa_hong": hoa_hong,
        "hoa_hong_uoc_tinh": round(so_ban * gia * hoa_hong / 100) if hoa_hong else None,
    }


def tinh_mot_ky(ky: dict, den_ngay: date, anh_chup: dict, thong_tin: dict) -> dict:
    cac_ngay_truoc = sorted(n for n in anh_chup if n < den_ngay)
    so_ngay_can = ky["so_ngay"]
    ket_qua = {"ten": ky["ten"], "so_ngay_can": so_ngay_can, "den_ngay": den_ngay.isoformat(),
               "tu_ngay": None, "so_ngay_co_du_lieu": 0, "nhom": [], "top_san_pham": [], "_ban": {}}
    if not cac_ngay_truoc or den_ngay not in anh_chup:
        return ket_qua

    # Mốc đầu kỳ: đúng 'so_ngay_can' ngày trước; chưa đủ dữ liệu thì dùng lần chụp sớm nhất
    ngay_dau = tim_anh_chup_truoc(cac_ngay_truoc, den_ngay - timedelta(days=so_ngay_can)) or cac_ngay_truoc[0]
    so_ngay_thuc = (den_ngay - ngay_dau).days
    ket_qua["tu_ngay"] = ngay_dau.isoformat()
    ket_qua["so_ngay_co_du_lieu"] = so_ngay_thuc
    ban_ky_nay = so_ban_giua(anh_chup[ngay_dau], anh_chup[den_ngay])
    ket_qua["_ban"] = ban_ky_nay

    # Kỳ trước liền kề (để biết số bán tăng hay giảm): chỉ tính khi kỳ này đã đủ ngày
    truoc_theo_nhom = None
    if so_ngay_thuc >= so_ngay_can:
        ngay_dau_ky_truoc = tim_anh_chup_truoc(cac_ngay_truoc, ngay_dau - timedelta(days=so_ngay_can))
        if ngay_dau_ky_truoc and (ngay_dau - ngay_dau_ky_truoc).days >= so_ngay_can:
            truoc_theo_nhom = {}
            for ma, so in so_ban_giua(anh_chup[ngay_dau_ky_truoc], anh_chup[ngay_dau]).items():
                ten_nhom = thong_tin.get(ma, {}).get("nhom")
                if ten_nhom:
                    truoc_theo_nhom[ten_nhom] = truoc_theo_nhom.get(ten_nhom, 0) + so

    # Cộng theo nhóm
    theo_nhom = {}
    for ma, so_ban in ban_ky_nay.items():
        ten_nhom = thong_tin.get(ma, {}).get("nhom")
        if not ten_nhom:
            continue
        n = theo_nhom.setdefault(ten_nhom, {"ten": ten_nhom, "so_ban": 0, "doanh_thu": 0, "so_san_pham": 0, "_sp": []})
        n["so_ban"] += so_ban
        n["doanh_thu"] += round(so_ban * thong_tin[ma].get("gia", 0))
        if so_ban > 0:
            n["so_san_pham"] += 1
        n["_sp"].append((so_ban, ma))

    tong_ban = sum(n["so_ban"] for n in theo_nhom.values()) or 1
    danh_sach_nhom = []
    for n in theo_nhom.values():
        n["ty_trong"] = round(n["so_ban"] * 100 / tong_ban, 1)
        n["so_ban_ky_truoc"] = None
        n["thay_doi_phan_tram"] = None
        if truoc_theo_nhom is not None:
            truoc = truoc_theo_nhom.get(n["ten"], 0)
            n["so_ban_ky_truoc"] = truoc
            if truoc > 0:
                n["thay_doi_phan_tram"] = round((n["so_ban"] - truoc) * 100 / truoc, 1)
        n["_sp"].sort(reverse=True)
        n["top_san_pham"] = [mo_ta_san_pham(ma, sb, thong_tin) for sb, ma in n["_sp"][:SO_SAN_PHAM_MOI_NHOM] if sb > 0]
        del n["_sp"]
        danh_sach_nhom.append(n)

    for i, n in enumerate(sorted(danh_sach_nhom, key=lambda x: x["doanh_thu"], reverse=True), 1):
        n["hang_doanh_thu"] = i
    danh_sach_nhom.sort(key=lambda x: x["so_ban"], reverse=True)
    for i, n in enumerate(danh_sach_nhom, 1):
        n["hang"] = i
        n["hang_so_ban"] = i
    ket_qua["nhom"] = danh_sach_nhom

    hang_dau = sorted(ban_ky_nay.items(), key=lambda x: x[1], reverse=True)[:SO_SAN_PHAM_HANG_DAU]
    ket_qua["top_san_pham"] = [mo_ta_san_pham(ma, sb, thong_tin) for ma, sb in hang_dau if sb > 0]
    return ket_qua


def cac_ngay_trong_ky(ky: dict) -> set:
    """Các ngày bán hàng nằm trong kỳ: từ sau ngày đầu kỳ đến hết ngày cuối kỳ."""
    if not ky or not ky.get("tu_ngay"):
        return set()
    dau, cuoi = date.fromisoformat(ky["tu_ngay"]), date.fromisoformat(ky["den_ngay"])
    return {dau + timedelta(days=i) for i in range(1, (cuoi - dau).days + 1)}


def gan_thay_doi_thu_hang(ky_nay: dict, ky_lan_truoc: dict, ngay_sale: dict):
    """So thứ hạng của cùng một kỳ giữa lần cập nhật này và lần trước, rồi gắn nhãn tín hiệu.
    thay_doi_hang > 0: tăng hạng (từ hạng 8 lên hạng 5 là +3); < 0: tụt hạng."""
    truoc = {n["ten"]: n for n in (ky_lan_truoc or {}).get("nhom", [])}
    ky_nay["co_so_sanh_hang"] = bool(truoc)

    # Ngày siêu sale vừa vào hoặc vừa ra khỏi kỳ → số liệu hai lần lệch nhau, không gắn nhãn
    ngay_lech = (cac_ngay_trong_ky(ky_nay) ^ cac_ngay_trong_ky(ky_lan_truoc)) & set(ngay_sale)
    ky_nay["ly_do_bo_tin_hieu"] = None
    if truoc and ngay_lech:
        ds = ", ".join(f"{ngay_sale[n]} ({n.strftime('%d/%m')})" for n in sorted(ngay_lech))
        ky_nay["ly_do_bo_tin_hieu"] = (f"Không gắn nhãn tín hiệu lần này vì {ds} vừa vào hoặc ra khỏi kỳ, "
                                       "số bán bị lệch bất thường. Mũi tên thứ hạng chỉ để tham khảo.")

    for n in ky_nay["nhom"]:
        cu = truoc.get(n["ten"])
        for kieu in ("so_ban", "doanh_thu"):
            hang_nay = n[f"hang_{kieu}"]
            hang_cu = cu[f"hang_{kieu}"] if cu else None
            n[f"hang_truoc_{kieu}"] = hang_cu
            n[f"thay_doi_hang_{kieu}"] = (hang_cu - hang_nay) if hang_cu else None
            nhan = None
            if hang_cu and not ky_nay["ly_do_bo_tin_hieu"]:
                thay_doi = hang_cu - hang_nay
                so_ban_giam_manh = (n["thay_doi_phan_tram"] is not None
                                    and n["thay_doi_phan_tram"] <= -PHAN_TRAM_GIAM_DANG_KE)
                # Tốp đầu đang giảm: lần trước ở tốp đầu, nay tụt hạng (kể cả văng khỏi tốp đầu)
                #                    hoặc vẫn ở tốp đầu nhưng số bán giảm mạnh
                if hang_cu <= TOP_DAU and (thay_doi < 0 or so_ban_giam_manh):
                    nhan = "tot_dau_dang_giam"
                # Đang vươn lên: lần trước ở ngoài tốp đầu, nay tăng từ 2 bậc trở lên (kể cả lọt vào tốp đầu)
                elif hang_cu > TOP_DAU and thay_doi >= SO_BAC_TANG_DANG_KE:
                    nhan = "dang_vuon_len"
            n[f"tin_hieu_{kieu}"] = nhan


def tinh_bung_no(ngay: date, anh_chup: dict, thong_tin: dict, ngay_sale: dict) -> dict:
    """Sản phẩm có số bán trong ngày gấp nhiều lần trung bình các ngày trước (bỏ ngày siêu sale)."""
    ket_qua = {"ly_do_bo_qua": None, "san_pham": []}
    if ngay in ngay_sale:
        ket_qua["ly_do_bo_qua"] = (f"Hôm nay là {ngay_sale[ngay]}, sản phẩm nào cũng bán vọt lên "
                                   "nên không xét sản phẩm bùng nổ.")
        return ket_qua
    cac_ngay = sorted(n for n in anh_chup if n <= ngay)
    if len(cac_ngay) < BUNG_NO_SO_NGAY_TOI_THIEU + 2 or cac_ngay[-1] != ngay:
        ket_qua["ly_do_bo_qua"] = f"Cần ít nhất {BUNG_NO_SO_NGAY_TOI_THIEU + 2} ngày dữ liệu để xét sản phẩm bùng nổ."
        return ket_qua

    # Số bán từng ngày = hiệu giữa hai lần chụp liền nhau, chia đều nếu hai lần chụp cách nhau nhiều ngày
    cac_cap = list(zip(cac_ngay[:-1], cac_ngay[1:]))
    hom_nay_dau, hom_nay_cuoi = cac_cap[-1]
    cap_truoc = [c for c in cac_cap[:-1] if c[1] not in ngay_sale][-BUNG_NO_SO_NGAY_SO_SANH:]

    for ma, cuoi in anh_chup[ngay].items():
        if ma not in anh_chup[hom_nay_dau]:
            continue
        ban_hom_nay = (cuoi - anh_chup[hom_nay_dau][ma]) / (hom_nay_cuoi - hom_nay_dau).days
        if ban_hom_nay < BUNG_NO_SO_BAN_TOI_THIEU:
            continue
        cac_gia_tri = [(anh_chup[c][ma] - anh_chup[d][ma]) / (c - d).days
                       for d, c in cap_truoc if ma in anh_chup[d] and ma in anh_chup[c]]
        if len(cac_gia_tri) < BUNG_NO_SO_NGAY_TOI_THIEU:
            continue
        trung_binh = max(sum(cac_gia_tri) / len(cac_gia_tri), 1)
        gap_lan = ban_hom_nay / trung_binh
        if gap_lan >= BUNG_NO_GAP_LAN:
            sp = mo_ta_san_pham(ma, round(ban_hom_nay), thong_tin)
            sp["trung_binh_truoc"] = round(trung_binh, 1)
            sp["gap_lan"] = round(gap_lan, 1)
            ket_qua["san_pham"].append(sp)

    ket_qua["san_pham"].sort(key=lambda s: s["gap_lan"], reverse=True)
    ket_qua["san_pham"] = ket_qua["san_pham"][:SO_SAN_PHAM_BUNG_NO]
    return ket_qua


def tinh_nen_quang_ba(ky_tuan: dict, thong_tin: dict) -> dict:
    """Sản phẩm mang lại hoa hồng ước tính cao nhất trong 7 ngày qua = số bán × giá × tỷ lệ hoa hồng."""
    ds = [mo_ta_san_pham(ma, so, thong_tin) for ma, so in ky_tuan["_ban"].items() if so > 0]
    ds = [s for s in ds if s["hoa_hong_uoc_tinh"]]
    if not ds:
        return {"ly_do_bo_qua": "Chưa có dữ liệu hoa hồng (cần ít nhất 2 ngày dữ liệu và Shopee trả tỷ lệ hoa hồng).",
                "so_ngay": ky_tuan["so_ngay_co_du_lieu"], "san_pham": []}
    ds.sort(key=lambda s: s["hoa_hong_uoc_tinh"], reverse=True)
    return {"ly_do_bo_qua": None, "so_ngay": ky_tuan["so_ngay_co_du_lieu"], "san_pham": ds[:SO_SAN_PHAM_NEN_QUANG_BA]}


FILE_LIEN_KET_SHOP = THU_MUC_DU_LIEU / "lien_ket_shop.json"
SO_LIEN_KET_MOI_TOI_DA = 150   # mỗi đêm tạo tối đa 150 link gian hàng mới (link cũ được lưu lại dùng tiếp)


def gan_lien_ket_gian_hang(phan_tich: dict, ham_lien_ket_shop):
    """Mỗi gian hàng uy tín cần một link tiếp thị liên kết. Ưu tiên link trang gian hàng;
    không tạo được thì dùng link sản phẩm bán chạy nhất của gian hàng đó (vẫn tính hoa hồng)."""
    da_luu = doc_json(FILE_LIEN_KET_SHOP, {})
    so_moi, loi_lien_tiep = 0, 0
    for nhom in phan_tich["nhom"].values():
        for gh in nhom.get("gian_hang", []):
            ma = gh.get("ma_shop")
            luu = da_luu.get(ma) if ma else None
            if isinstance(luu, str):                      # bản lưu cũ chỉ có link
                luu = {"lien_ket": luu, "logo": ""}
            # Chưa có link, hoặc bản lưu cũ chưa từng thử lấy logo thì hỏi Shopee
            if ma and (not luu or not luu.get("da_thu_logo")) and so_moi < SO_LIEN_KET_MOI_TOI_DA and loi_lien_tiep < 5:
                try:
                    luu = ham_lien_ket_shop(ma)
                    if isinstance(luu, str):
                        luu = {"lien_ket": luu, "logo": ""}
                    luu["da_thu_logo"] = True
                    da_luu[ma] = luu
                    so_moi += 1
                    loi_lien_tiep = 0
                    time.sleep(NGHI_KHI_HOI_TUNG_SAN_PHAM)
                except Exception as loi:
                    luu = da_luu.get(ma) if isinstance(da_luu.get(ma), dict) else None   # giữ link cũ nếu có
                    loi_lien_tiep += 1
                    if loi_lien_tiep == 5:
                        print(f"  Không tạo được link gian hàng ({loi}). Tạm dùng link sản phẩm của gian hàng.")
            lien_ket = (luu or {}).get("lien_ket")
            gh["lien_ket"] = lien_ket or gh.get("lien_ket_san_pham") or ""
            gh["la_link_gian_hang"] = bool(lien_ket)
            # Ảnh gian hàng: logo thật của gian hàng; chưa có logo thì dùng ảnh thật sản phẩm bán chạy nhất của gian hàng
            gh["logo"] = (luu or {}).get("logo") or ""
    ghi_json(FILE_LIEN_KET_SHOP, da_luu)
    if so_moi:
        print(f"Đã tạo {so_moi} link gian hàng mới.")


def tinh_xep_hang(ngay: date, ham_lien_ket_shop=None):
    ham_lien_ket_shop = ham_lien_ket_shop or tao_lien_ket_shop
    anh_chup = doc_tat_ca_anh_chup()
    thong_tin = doc_json(FILE_SAN_PHAM, {})
    ngay_sale = doc_ngay_khuyen_mai()

    cac_ngay_truoc = [n for n in anh_chup if n < ngay]
    ngay_lan_truoc = max(cac_ngay_truoc) if cac_ngay_truoc else None
    anh_chup_lan_truoc = {n: v for n, v in anh_chup.items() if n <= ngay_lan_truoc} if ngay_lan_truoc else {}

    cac_ky = {}
    for ky in CAC_KY:
        ky_nay = tinh_mot_ky(ky, ngay, anh_chup, thong_tin)
        ky_lan_truoc = tinh_mot_ky(ky, ngay_lan_truoc, anh_chup_lan_truoc, thong_tin) if ngay_lan_truoc else None
        gan_thay_doi_thu_hang(ky_nay, ky_lan_truoc, ngay_sale)
        cac_ky[ky["ma"]] = ky_nay

    nen_quang_ba = tinh_nen_quang_ba(cac_ky["tuan"], thong_tin)
    for ky in cac_ky.values():
        del ky["_ban"]

    sale_sap_toi = sorted((n, t) for n, t in ngay_sale.items() if ngay < n <= ngay + timedelta(days=7))
    bang = {
        "cap_nhat_luc": datetime.now(GIO_VIET_NAM).strftime("%H:%M ngày %d/%m/%Y"),
        "ngay": ngay.isoformat(),
        "ngay_lan_truoc": ngay_lan_truoc.isoformat() if ngay_lan_truoc else None,
        "so_san_pham_theo_doi": len(anh_chup.get(ngay, {})),
        "ngay_sale": ngay_sale.get(ngay),
        "sale_sap_toi": [{"ngay": n.isoformat(), "ten": t} for n, t in sale_sap_toi],
        "ky": cac_ky,
        "bung_no": tinh_bung_no(ngay, anh_chup, thong_tin, ngay_sale),
        "nen_quang_ba": nen_quang_ba,
    }

    # Phân tích, định hướng, lời khuyên cho từng nhóm và từng sản phẩm có trên trang
    ma_can = set()
    for ky in cac_ky.values():
        ma_can.update(s["ma"] for s in ky["top_san_pham"])
        for n in ky["nhom"]:
            ma_can.update(s["ma"] for s in n["top_san_pham"])
    ma_can.update(s["ma"] for s in bang["bung_no"]["san_pham"])
    ma_can.update(s["ma"] for s in nen_quang_ba["san_pham"])
    bang["phan_tich"] = phan_tich_toan_bo(ngay, anh_chup, thong_tin, ngay_sale, ma_can)
    gan_lien_ket_gian_hang(bang["phan_tich"], ham_lien_ket_shop)

    ghi_json(FILE_XEP_HANG, bang, gon=True)
    return bang


# ======================= BƯỚC 3: GỬI TELEGRAM =======================
def dinh_dang_so(so) -> str:
    return f"{int(round(so)):,}".replace(",", ".")


def dinh_dang_tien(so) -> str:
    if so >= 1e9:
        return f"{so / 1e9:.1f} tỷ".replace(".", ",")
    if so >= 1e6:
        return f"{so / 1e6:.1f} triệu".replace(".", ",")
    return f"{dinh_dang_so(so)} đ"


def gui_telegram(bang: dict):
    ma_bot = os.environ.get("TELEGRAM_BOT_TOKEN")
    ma_nguoi_nhan = os.environ.get("TELEGRAM_CHAT_ID")
    if not ma_bot or not ma_nguoi_nhan:
        print("Chưa có mã Telegram, bỏ qua bước gửi tin.")
        return
    e = html.escape
    ngay = date.fromisoformat(bang["ngay"])
    ky = bang["ky"]["ngay"]
    dong = [f"<b>NHÓM HÀNG BÁN CHẠY SHOPEE – NGÀY {ngay.strftime('%d/%m/%Y')}</b>"]
    if bang["ngay_sale"]:
        dong.append(f"⚠️ Ngày {e(bang['ngay_sale'])}: số bán cao bất thường, không so sánh với ngày thường.")

    if not ky["nhom"]:
        dong.append("Mới có ngày dữ liệu đầu tiên. Lần cập nhật sau mới tính được số bán.")
    else:
        for n in ky["nhom"][:10]:
            d = n.get("thay_doi_hang_so_ban")
            mui_ten = "" if d is None else (f" ⬆{d}" if d > 0 else (f" ⬇{-d}" if d < 0 else " ="))
            dong.append(f"{n['hang']}. {e(n['ten'])}: {dinh_dang_so(n['so_ban'])} sp{mui_ten}")

    # Tín hiệu: ưu tiên theo 7 ngày (ổn định hơn), không có thì theo ngày
    for ma_ky in ("tuan", "ngay"):
        k = bang["ky"][ma_ky]
        len_ = [n for n in k["nhom"] if n.get("tin_hieu_so_ban") == "dang_vuon_len"]
        giam = [n for n in k["nhom"] if n.get("tin_hieu_so_ban") == "tot_dau_dang_giam"]
        if len_ or giam:
            dong += ["", f"<b>Tín hiệu ({k['ten'].lower()})</b>"]
            dong += [f"🟢 Đang vươn lên: {e(n['ten'])} (hạng {n['hang_truoc_so_ban']} → {n['hang']})" for n in len_]
            for n in giam:
                pt = n["thay_doi_phan_tram"]
                them = f", số bán {pt:+}%".replace(".", ",") if pt is not None else ""
                dong.append(f"🟠 Tốp đầu đang giảm: {e(n['ten'])} (hạng {n['hang_truoc_so_ban']} → {n['hang']}{them})")
            break

    bung_no = bang["bung_no"]["san_pham"][:5]
    if bung_no:
        dong += ["", "<b>🔥 Sản phẩm đang bùng nổ</b>"]
        dong += [f"• {e(s['ten'][:55])} – {dinh_dang_so(s['so_ban'])} sp, gấp {str(s['gap_lan']).replace('.', ',')} lần"
                 for s in bung_no]

    nen = bang["nen_quang_ba"]["san_pham"][:10]
    if nen:
        dong += ["", f"<b>💰 Nên quảng bá (hoa hồng cao nhất {bang['nen_quang_ba']['so_ngay']} ngày qua)</b>"]
        for i, s in enumerate(nen, 1):
            ten = e(s["ten"][:55])
            dau = f'<a href="{e(s["duong_dan"])}">{ten}</a>' if s["duong_dan"] else ten
            dong.append(f"{i}. {dau} – {dinh_dang_tien(s['gia'])}, hoa hồng {str(s['hoa_hong']).replace('.', ',')}%")

    for s in bang["sale_sap_toi"]:
        dong += ["", f"📅 Sắp tới: {e(s['ten'])} ngày {date.fromisoformat(s['ngay']).strftime('%d/%m')}"]

    requests.post(f"https://api.telegram.org/bot{ma_bot}/sendMessage",
                  data={"chat_id": ma_nguoi_nhan, "text": "\n".join(dong)[:4000], "parse_mode": "HTML",
                        "disable_web_page_preview": "true"}, timeout=30)
    print("Đã gửi Telegram.")


# ======================= CHẠY =======================
def ngay_can_ghi() -> date:
    """Chạy lúc 0 giờ 13 đêm thì ảnh chụp tính cho ngày vừa kết thúc (hôm qua).
    Bấm chạy tay ban ngày (sau 6 giờ sáng) thì ghi cho hôm nay; đêm đó chạy lại sẽ ghi đè bằng số trọn ngày."""
    bay_gio = datetime.now(GIO_VIET_NAM)
    return (bay_gio - timedelta(hours=6)).date()


def chay(ngay: date = None, ham_theo_tu_khoa=lay_theo_tu_khoa, ham_theo_ma=lay_theo_ma, gui_tin=True, ham_lien_ket_shop=None):
    ngay = ngay or ngay_can_ghi()
    print(f"=== Bắt đầu cập nhật, tính đến hết ngày {ngay.isoformat()} ===")
    thu_thap(ngay, ham_theo_tu_khoa, ham_theo_ma)
    bang = tinh_xep_hang(ngay, ham_lien_ket_shop)
    if gui_tin:
        gui_telegram(bang)
    print("=== Xong ===")


if __name__ == "__main__":
    try:
        chay()
    except Exception as loi:
        print(f"LỖI: {loi}")
        sys.exit(1)
