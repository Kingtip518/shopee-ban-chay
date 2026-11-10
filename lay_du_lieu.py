# -*- coding: utf-8 -*-
"""
LẤY DỮ LIỆU BÁN CHẠY SHOPEE – CHẠY MỖI SÁNG MỘT LẦN

Cách hoạt động:
1. Với từng nhóm hàng trong file nhom_hang.json, lấy các sản phẩm bán chạy nhất
   theo từng từ khóa, qua cổng dữ liệu chính thức của chương trình
   Tiếp thị liên kết Shopee (Shopee Affiliate).
2. Shopee chỉ cho biết "tổng số đã bán từ trước tới nay" của mỗi sản phẩm.
   Vì vậy mỗi ngày chương trình "chụp" lại con số đó, lưu vào du_lieu/anh_chup/.
   Số bán trong ngày  = số đã bán hôm nay  − số đã bán hôm qua
   Số bán trong tuần  = số đã bán hôm nay  − số đã bán 7 ngày trước
   Số bán trong tháng = số đã bán hôm nay  − số đã bán 30 ngày trước
3. Cộng theo nhóm hàng, xếp hạng, ghi ra du_lieu/bang_xep_hang.json cho trang web đọc.
4. Gửi bảng xếp hạng hôm nay về Telegram.

Các mã bí mật lấy từ biến môi trường (đặt trong mục Secrets của GitHub):
  SHOPEE_APP_ID       : mã ứng dụng tiếp thị liên kết Shopee
  SHOPEE_SECRET       : khóa bí mật tiếp thị liên kết Shopee
  TELEGRAM_BOT_TOKEN  : mã của con bot Telegram (không có thì bỏ qua bước gửi)
  TELEGRAM_CHAT_ID    : mã cuộc trò chuyện nhận tin (không có thì bỏ qua bước gửi)
"""

import hashlib
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# ---------------- THÔNG SỐ ----------------
THU_MUC = Path(__file__).resolve().parent
FILE_NHOM_HANG = THU_MUC / "nhom_hang.json"
THU_MUC_DU_LIEU = THU_MUC / "du_lieu"
THU_MUC_ANH_CHUP = THU_MUC_DU_LIEU / "anh_chup"
FILE_SAN_PHAM = THU_MUC_DU_LIEU / "san_pham.json"
FILE_XEP_HANG = THU_MUC_DU_LIEU / "bang_xep_hang.json"

DIA_CHI_SHOPEE = "https://open-api.affiliate.shopee.vn/graphql"
SO_SAN_PHAM_MOI_TRANG = 50      # mỗi lần hỏi Shopee lấy 50 sản phẩm
SO_TRANG_MOI_TU_KHOA = 2        # mỗi từ khóa lấy 2 trang = 100 sản phẩm bán chạy nhất
NGHI_GIUA_CAC_LAN_HOI = 1.0     # nghỉ 1 giây giữa hai lần hỏi để không bị Shopee chặn
SO_NGAY_GIU_ANH_CHUP = 70       # giữ ảnh chụp 70 ngày (đủ để so tháng này với tháng trước)
SO_SAN_PHAM_HANG_DAU = 30       # số sản phẩm hiển thị trong bảng sản phẩm bán chạy nhất
SO_SAN_PHAM_MOI_NHOM = 10       # số sản phẩm hiển thị khi bấm vào một nhóm

GIO_VIET_NAM = timezone(timedelta(hours=7))

CAC_KY = [
    {"ma": "ngay", "ten": "Hôm nay", "so_ngay": 1},
    {"ma": "tuan", "ten": "7 ngày qua", "so_ngay": 7},
    {"ma": "thang", "ten": "30 ngày qua", "so_ngay": 30},
]


# ---------------- HỎI DỮ LIỆU SHOPEE ----------------
def hoi_shopee(cau_hoi: str) -> dict:
    """Gửi một câu hỏi tới cổng dữ liệu tiếp thị liên kết Shopee, có ký xác thực."""
    ma_ung_dung = os.environ["SHOPEE_APP_ID"]
    khoa_bi_mat = os.environ["SHOPEE_SECRET"]
    noi_dung = json.dumps({"query": cau_hoi}, ensure_ascii=False, separators=(",", ":"))
    moc_gio = str(int(time.time()))
    chu_ky = hashlib.sha256(
        (ma_ung_dung + moc_gio + noi_dung + khoa_bi_mat).encode("utf-8")
    ).hexdigest()
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


def lay_san_pham_ban_chay(tu_khoa: str, trang: int) -> list:
    """Lấy một trang sản phẩm theo từ khóa, xếp theo số đã bán từ cao xuống thấp (sortType 2)."""
    cau_hoi = (
        "{productOfferV2(keyword:%s,sortType:2,page:%d,limit:%d){"
        "nodes{itemId productName priceMin priceMax sales ratingStar imageUrl "
        "offerLink productLink shopName productCatIds}"
        "pageInfo{page limit hasNextPage}}}"
        % (json.dumps(tu_khoa, ensure_ascii=False), trang, SO_SAN_PHAM_MOI_TRANG)
    )
    du_lieu = hoi_shopee(cau_hoi)
    return du_lieu["productOfferV2"]["nodes"] or []


# ---------------- ĐỌC / GHI FILE ----------------
def doc_json(duong_dan: Path, mac_dinh):
    if duong_dan.exists():
        return json.loads(duong_dan.read_text(encoding="utf-8"))
    return mac_dinh


def ghi_json(duong_dan: Path, du_lieu):
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    duong_dan.write_text(json.dumps(du_lieu, ensure_ascii=False, indent=1), encoding="utf-8")


def doc_tat_ca_anh_chup() -> dict:
    """Trả về {ngày: {mã sản phẩm: tổng đã bán}}."""
    ket_qua = {}
    for file in sorted(THU_MUC_ANH_CHUP.glob("*.json")):
        ngay = date.fromisoformat(file.stem)
        ket_qua[ngay] = doc_json(file, {}).get("da_ban", {})
    return ket_qua


def doi_so(gia_tri) -> float:
    try:
        return float(gia_tri)
    except (TypeError, ValueError):
        return 0.0


# ---------------- BƯỚC 1: THU THẬP HÔM NAY ----------------
def thu_thap_hom_nay(hom_nay: date, ham_lay=lay_san_pham_ban_chay):
    cau_hinh = doc_json(FILE_NHOM_HANG, {"nhom_hang": []})
    thong_tin_san_pham = doc_json(FILE_SAN_PHAM, {})
    da_ban_hom_nay = {}
    so_lan_loi = 0

    for nhom in cau_hinh["nhom_hang"]:
        for tu_khoa in nhom["tu_khoa"]:
            for trang in range(1, SO_TRANG_MOI_TU_KHOA + 1):
                try:
                    danh_sach = ham_lay(tu_khoa, trang)
                except Exception as loi:
                    so_lan_loi += 1
                    print(f"  Lỗi khi lấy '{tu_khoa}' trang {trang}: {loi}")
                    break
                for sp in danh_sach:
                    ma = str(sp["itemId"])
                    da_ban_hom_nay[ma] = int(sp.get("sales") or 0)
                    cu = thong_tin_san_pham.get(ma, {})
                    thong_tin_san_pham[ma] = {
                        "ten": sp.get("productName", ""),
                        "gia": doi_so(sp.get("priceMin")),
                        "gia_cao_nhat": doi_so(sp.get("priceMax")),
                        "danh_gia": doi_so(sp.get("ratingStar")),
                        "anh": sp.get("imageUrl", ""),
                        "duong_dan": sp.get("offerLink") or sp.get("productLink", ""),
                        "cua_hang": sp.get("shopName", ""),
                        # Sản phẩm thuộc nhóm nào thì giữ nhóm được gán lần đầu, tránh nhảy nhóm
                        "nhom": cu.get("nhom", nhom["ten"]),
                        "lan_cuoi_thay": hom_nay.isoformat(),
                    }
                print(f"  {nhom['ten']} | {tu_khoa} | trang {trang}: {len(danh_sach)} sản phẩm")
                if len(danh_sach) < SO_SAN_PHAM_MOI_TRANG:
                    break
                time.sleep(NGHI_GIUA_CAC_LAN_HOI)

    if not da_ban_hom_nay:
        raise RuntimeError(f"Không lấy được sản phẩm nào (số lần lỗi: {so_lan_loi}). Không ghi ảnh chụp hôm nay.")

    # Bỏ những sản phẩm lâu không còn xuất hiện
    gioi_han = (hom_nay - timedelta(days=SO_NGAY_GIU_ANH_CHUP)).isoformat()
    thong_tin_san_pham = {m: v for m, v in thong_tin_san_pham.items() if v["lan_cuoi_thay"] >= gioi_han}

    ghi_json(THU_MUC_ANH_CHUP / f"{hom_nay.isoformat()}.json",
             {"ngay": hom_nay.isoformat(), "da_ban": da_ban_hom_nay})
    ghi_json(FILE_SAN_PHAM, thong_tin_san_pham)

    # Xóa ảnh chụp quá cũ
    for file in THU_MUC_ANH_CHUP.glob("*.json"):
        if file.stem < gioi_han:
            file.unlink()

    print(f"Đã chụp {len(da_ban_hom_nay)} sản phẩm ngày {hom_nay.isoformat()}")


# ---------------- BƯỚC 2: TÍNH XẾP HẠNG ----------------
def tim_anh_chup_truoc(cac_ngay: list, moc: date):
    """Tìm ảnh chụp gần nhất vào đúng hoặc trước ngày mốc."""
    phu_hop = [n for n in cac_ngay if n <= moc]
    return max(phu_hop) if phu_hop else None


def so_ban_giua(anh_dau: dict, anh_cuoi: dict) -> dict:
    """Số bán của từng sản phẩm giữa hai lần chụp. Chỉ tính sản phẩm có mặt ở cả hai lần."""
    ket_qua = {}
    for ma, cuoi in anh_cuoi.items():
        if ma in anh_dau:
            ket_qua[ma] = max(0, cuoi - anh_dau[ma])
    return ket_qua


def tinh_mot_ky(ky: dict, hom_nay: date, anh_chup: dict, thong_tin: dict) -> dict:
    cac_ngay = sorted(anh_chup)
    cac_ngay_truoc = [n for n in cac_ngay if n < hom_nay]
    so_ngay_can = ky["so_ngay"]

    ket_qua = {"ten": ky["ten"], "so_ngay_can": so_ngay_can, "den_ngay": hom_nay.isoformat(),
               "nhom": [], "top_san_pham": []}

    if not cac_ngay_truoc:
        ket_qua["so_ngay_co_du_lieu"] = 0
        ket_qua["tu_ngay"] = None
        return ket_qua

    # Mốc đầu kỳ: đúng 'so_ngay_can' ngày trước; nếu chưa đủ dữ liệu thì dùng lần chụp sớm nhất
    ngay_dau = tim_anh_chup_truoc(cac_ngay_truoc, hom_nay - timedelta(days=so_ngay_can)) or cac_ngay_truoc[0]
    so_ngay_thuc = (hom_nay - ngay_dau).days
    ket_qua["tu_ngay"] = ngay_dau.isoformat()
    ket_qua["so_ngay_co_du_lieu"] = so_ngay_thuc

    ban_ky_nay = so_ban_giua(anh_chup[ngay_dau], anh_chup[hom_nay])

    # Kỳ trước (để biết nhóm nào đang tăng, nhóm nào đang giảm): chỉ tính khi kỳ này đã đủ ngày
    ban_ky_truoc = None
    if so_ngay_thuc >= so_ngay_can:
        ngay_dau_ky_truoc = tim_anh_chup_truoc(cac_ngay_truoc, ngay_dau - timedelta(days=so_ngay_can))
        if ngay_dau_ky_truoc and (ngay_dau - ngay_dau_ky_truoc).days >= so_ngay_can:
            ban_ky_truoc = so_ban_giua(anh_chup[ngay_dau_ky_truoc], anh_chup[ngay_dau])

    def mo_ta_san_pham(ma, so_ban):
        tt = thong_tin.get(ma, {})
        return {
            "ma": ma, "ten": tt.get("ten", ""), "nhom": tt.get("nhom", ""),
            "gia": tt.get("gia", 0), "danh_gia": tt.get("danh_gia", 0),
            "anh": tt.get("anh", ""), "duong_dan": tt.get("duong_dan", ""),
            "cua_hang": tt.get("cua_hang", ""), "so_ban": so_ban,
            "doanh_thu": round(so_ban * tt.get("gia", 0)),
        }

    # Cộng theo nhóm
    theo_nhom = {}
    for ma, so_ban in ban_ky_nay.items():
        ten_nhom = thong_tin.get(ma, {}).get("nhom")
        if not ten_nhom:
            continue
        n = theo_nhom.setdefault(ten_nhom, {"ten": ten_nhom, "so_ban": 0, "doanh_thu": 0,
                                            "so_san_pham": 0, "_sp": []})
        n["so_ban"] += so_ban
        n["doanh_thu"] += round(so_ban * thong_tin[ma].get("gia", 0))
        n["so_san_pham"] += 1
        n["_sp"].append((so_ban, ma))

    if ban_ky_truoc is not None:
        truoc_theo_nhom = {}
        for ma, so_ban in ban_ky_truoc.items():
            ten_nhom = thong_tin.get(ma, {}).get("nhom")
            if ten_nhom:
                truoc_theo_nhom[ten_nhom] = truoc_theo_nhom.get(ten_nhom, 0) + so_ban

    tong_ban = sum(n["so_ban"] for n in theo_nhom.values()) or 1
    danh_sach_nhom = []
    for n in theo_nhom.values():
        n["ty_trong"] = round(n["so_ban"] * 100 / tong_ban, 1)
        n["so_ban_ky_truoc"] = None
        n["thay_doi_phan_tram"] = None
        if ban_ky_truoc is not None:
            truoc = truoc_theo_nhom.get(n["ten"], 0)
            n["so_ban_ky_truoc"] = truoc
            if truoc > 0:
                n["thay_doi_phan_tram"] = round((n["so_ban"] - truoc) * 100 / truoc, 1)
        n["_sp"].sort(reverse=True)
        n["top_san_pham"] = [mo_ta_san_pham(ma, sb) for sb, ma in n["_sp"][:SO_SAN_PHAM_MOI_NHOM] if sb > 0]
        del n["_sp"]
        danh_sach_nhom.append(n)

    # Thứ hạng theo doanh thu
    for i, n in enumerate(sorted(danh_sach_nhom, key=lambda x: x["doanh_thu"], reverse=True), 1):
        n["hang_doanh_thu"] = i
    # Thứ hạng theo số lượng bán (thứ tự mặc định)
    danh_sach_nhom.sort(key=lambda x: x["so_ban"], reverse=True)
    for i, n in enumerate(danh_sach_nhom, 1):
        n["hang"] = i
        n["hang_so_ban"] = i
    ket_qua["nhom"] = danh_sach_nhom

    hang_dau = sorted(ban_ky_nay.items(), key=lambda x: x[1], reverse=True)[:SO_SAN_PHAM_HANG_DAU]
    ket_qua["top_san_pham"] = [mo_ta_san_pham(ma, sb) for ma, sb in hang_dau if sb > 0]
    return ket_qua


TOP_DAU = 5                    # nhóm đứng hạng 1–5 được coi là "tốp đầu"
SO_BAC_TANG_DANG_KE = 2        # nhóm từ ngoài tốp đầu tăng từ 2 bậc trở lên thì gắn nhãn "đang vươn lên"
PHAN_TRAM_GIAM_DANG_KE = 10    # nhóm tốp đầu có số bán giảm từ 10% trở lên so với kỳ trước thì coi là đang giảm


def gan_thay_doi_thu_hang(ky_nay: dict, ky_lan_truoc: dict):
    """So thứ hạng của cùng một kỳ giữa lần cập nhật này và lần cập nhật trước, rồi gắn nhãn tín hiệu.
    thay_doi_hang > 0: tăng hạng (ví dụ từ hạng 8 lên hạng 5 là +3); < 0: tụt hạng."""
    truoc = {n["ten"]: n for n in (ky_lan_truoc or {}).get("nhom", [])}
    ky_nay["co_so_sanh_hang"] = bool(truoc)
    for n in ky_nay["nhom"]:
        cu = truoc.get(n["ten"])
        for kieu in ("so_ban", "doanh_thu"):
            hang_nay = n[f"hang_{kieu}"]
            hang_cu = cu[f"hang_{kieu}"] if cu else None
            n[f"hang_truoc_{kieu}"] = hang_cu
            n[f"thay_doi_hang_{kieu}"] = (hang_cu - hang_nay) if hang_cu else None
            # Nhãn tín hiệu
            nhan = None
            if hang_cu:
                thay_doi = hang_cu - hang_nay
                so_ban_giam_manh = (n["thay_doi_phan_tram"] is not None
                                    and n["thay_doi_phan_tram"] <= -PHAN_TRAM_GIAM_DANG_KE)
                # Tốp đầu đang giảm: lần trước đang ở tốp đầu, nay tụt hạng (kể cả văng khỏi tốp đầu)
                #                    hoặc vẫn ở tốp đầu nhưng số bán giảm mạnh
                if hang_cu <= TOP_DAU and (thay_doi < 0 or so_ban_giam_manh):
                    nhan = "tot_dau_dang_giam"
                # Đang vươn lên: lần trước ở ngoài tốp đầu, nay tăng từ 2 bậc trở lên (kể cả lọt vào tốp đầu)
                elif hang_cu > TOP_DAU and thay_doi >= SO_BAC_TANG_DANG_KE:
                    nhan = "dang_vuon_len"
            n[f"tin_hieu_{kieu}"] = nhan


def tinh_xep_hang(hom_nay: date):
    anh_chup = doc_tat_ca_anh_chup()
    thong_tin = doc_json(FILE_SAN_PHAM, {})

    # Lần cập nhật trước = lần chụp gần nhất trước hôm nay
    cac_ngay_truoc = [n for n in anh_chup if n < hom_nay]
    ngay_lan_truoc = max(cac_ngay_truoc) if cac_ngay_truoc else None
    anh_chup_lan_truoc = {n: v for n, v in anh_chup.items() if n <= ngay_lan_truoc} if ngay_lan_truoc else {}

    cac_ky = {}
    for ky in CAC_KY:
        ky_nay = tinh_mot_ky(ky, hom_nay, anh_chup, thong_tin)
        ky_lan_truoc = tinh_mot_ky(ky, ngay_lan_truoc, anh_chup_lan_truoc, thong_tin) if ngay_lan_truoc else None
        gan_thay_doi_thu_hang(ky_nay, ky_lan_truoc)
        cac_ky[ky["ma"]] = ky_nay

    bang = {
        "cap_nhat_luc": datetime.now(GIO_VIET_NAM).strftime("%H:%M ngày %d/%m/%Y"),
        "ngay": hom_nay.isoformat(),
        "ngay_lan_truoc": ngay_lan_truoc.isoformat() if ngay_lan_truoc else None,
        "so_san_pham_theo_doi": len(anh_chup.get(hom_nay, {})),
        "ky": cac_ky,
    }
    ghi_json(FILE_XEP_HANG, bang)
    return bang


# ---------------- BƯỚC 3: GỬI TELEGRAM ----------------
def dinh_dang_so(so) -> str:
    return f"{int(so):,}".replace(",", ".")


def gui_telegram(bang: dict):
    ma_bot = os.environ.get("TELEGRAM_BOT_TOKEN")
    ma_nguoi_nhan = os.environ.get("TELEGRAM_CHAT_ID")
    if not ma_bot or not ma_nguoi_nhan:
        print("Chưa có mã Telegram, bỏ qua bước gửi tin.")
        return

    ky = bang["ky"]["ngay"]
    dong = [f"<b>NHÓM HÀNG BÁN CHẠY SHOPEE – {ky['den_ngay']}</b>"]
    if not ky["nhom"]:
        dong.append("Mới có ngày dữ liệu đầu tiên. Từ ngày mai mới tính được số bán trong ngày.")
    else:
        for n in ky["nhom"][:10]:
            doi_hang = n.get("thay_doi_hang_so_ban")
            if doi_hang is None:
                mui_ten = ""
            elif doi_hang > 0:
                mui_ten = f" (⬆{doi_hang} bậc)"
            elif doi_hang < 0:
                mui_ten = f" (⬇{-doi_hang} bậc)"
            else:
                mui_ten = " (giữ hạng)"
            dong.append(f"{n['hang']}. {n['ten']}: {dinh_dang_so(n['so_ban'])} sp{mui_ten}")

    # Tín hiệu đáng chú ý theo 7 ngày qua (ổn định hơn theo ngày)
    for ma_ky in ("tuan", "ngay"):
        k = bang["ky"][ma_ky]
        len_ = [n for n in k["nhom"] if n.get("tin_hieu_so_ban") == "dang_vuon_len"]
        giam = [n for n in k["nhom"] if n.get("tin_hieu_so_ban") == "tot_dau_dang_giam"]
        if len_ or giam:
            dong.append("")
            dong.append(f"<b>Tín hiệu ({k['ten'].lower()})</b>")
            for n in len_:
                dong.append(f"🟢 Đang vươn lên: {n['ten']} (hạng {n['hang_truoc_so_ban']} → {n['hang']})")
            for n in giam:
                phan_tram = (f", số bán {n['thay_doi_phan_tram']:+}%".replace(".", ",")
                             if n["thay_doi_phan_tram"] is not None else "")
                dong.append(f"🟠 Tốp đầu đang giảm: {n['ten']} (hạng {n['hang_truoc_so_ban']} → {n['hang']}{phan_tram})")
            break
    if ky["nhom"]:
        dong.append("")
        dong.append("<b>5 sản phẩm bán nhiều nhất hôm nay</b>")
        for i, sp in enumerate(ky["top_san_pham"][:5], 1):
            dong.append(f"{i}. {sp['ten'][:60]} – {dinh_dang_so(sp['so_ban'])} sp")

    tuan = bang["ky"]["tuan"]
    if tuan["nhom"]:
        dong.append("")
        dong.append(f"<b>Dẫn đầu {tuan['so_ngay_co_du_lieu']} ngày qua:</b> "
                    + ", ".join(n["ten"] for n in tuan["nhom"][:3]))

    requests.post(f"https://api.telegram.org/bot{ma_bot}/sendMessage",
                  data={"chat_id": ma_nguoi_nhan, "text": "\n".join(dong), "parse_mode": "HTML",
                        "disable_web_page_preview": "true"}, timeout=30)
    print("Đã gửi Telegram.")


# ---------------- CHẠY ----------------
def chay(hom_nay: date = None, ham_lay=lay_san_pham_ban_chay, gui_tin=True):
    hom_nay = hom_nay or datetime.now(GIO_VIET_NAM).date()
    print(f"=== Bắt đầu cập nhật ngày {hom_nay.isoformat()} ===")
    thu_thap_hom_nay(hom_nay, ham_lay)
    bang = tinh_xep_hang(hom_nay)
    if gui_tin:
        gui_telegram(bang)
    print("=== Xong ===")


if __name__ == "__main__":
    try:
        chay()
    except Exception as loi:
        print(f"LỖI: {loi}")
        sys.exit(1)
