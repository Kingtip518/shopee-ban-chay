# -*- coding: utf-8 -*-
"""
PHÂN TÍCH VÀ LỜI KHUYÊN CHO TỪNG NHÓM HÀNG, TỪNG SẢN PHẨM

Từ các ảnh chụp "tổng đã bán" mỗi ngày, tính ra:
  - Chuỗi số bán từng ngày trong 30 ngày gần nhất (vẽ biểu đồ)
  - Giai đoạn: mới nổi / đang tăng / đang chững / ổn định / đang giảm / thoái trào
  - Độ cạnh tranh: số shop cùng bán, phần trăm số bán của 3 shop đứng đầu
  - Khoảng giá bán chạy (tính theo số lượng bán, không phải theo số sản phẩm)
  - Lời khuyên viết sẵn theo từng tình huống
Ngày siêu sale không được dùng để tính giai đoạn (số bán ngày đó cao bất thường).
"""

from datetime import date, timedelta

# ======================= THÔNG SỐ (sửa số ở đây nếu muốn) =======================
SO_NGAY_BIEU_DO = 30          # biểu đồ số bán 30 ngày gần nhất
SO_NGAY_TOI_THIEU = 8         # cần ít nhất 8 ngày số bán mới xác định được giai đoạn

# Giai đoạn, dựa trên "tăng so với tuần trước" (trung bình 7 ngày gần nhất so với 7 ngày trước đó)
# và "đà gần đây" (trung bình 3 ngày gần nhất so với 4 ngày trước đó)
MOI_NOI_TANG_TUAN = 30        # tăng từ 30% trở lên so với tuần trước và đà không giảm → mới nổi
DANG_TANG_TANG_TUAN = 10      # tăng từ 10% trở lên → đang tăng (đà chậm lại hơn 5% → đang chững)
DA_CHAM_LAI = -5              # đà 3 ngày gần nhất giảm hơn 5% so với 4 ngày trước → đang chậm lại
DANG_GIAM_TUAN = -5           # giảm hơn 5% so với tuần trước → đang giảm
THOAI_TRAO_TUAN = -15         # giảm từ 15% trở lên so với tuần trước → thoái trào

# Độ cạnh tranh, dựa trên phần trăm số bán của 3 shop đứng đầu trong 7 ngày qua
CANH_TRANH_CAO = 60           # 3 shop đầu chiếm từ 60% trở lên → cạnh tranh cao (vài shop lớn nắm thị trường)
CANH_TRANH_THAP = 35          # 3 shop đầu chiếm dưới 35% → cạnh tranh thấp (nhiều shop cùng chia, dễ chen chân)

SO_NGAY_NHAC_SALE = 21

# Gian hàng uy tín cho từng ngành (để gắn link tiếp thị liên kết)
SO_GIAN_HANG_MOI_NGANH = 5      # mỗi ngành hiện 5 gian hàng uy tín nhất
DANH_GIA_TOI_THIEU = 4.7        # điểm đánh giá trung bình phải từ 4,7 sao (Shopee Mall: từ 4,5 sao)
DANH_GIA_TOI_THIEU_MALL = 4.5
SO_BAN_TOI_THIEU_7_NGAY = 30    # phải bán được ít nhất 30 sản phẩm trong 7 ngày qua        # nhắc ngày siêu sale nếu còn trong vòng 21 ngày tới

GIAI_DOAN = {
    "moi_noi":    {"ten": "Mới nổi",          "mau": "len"},
    "dang_tang":  {"ten": "Đang tăng",        "mau": "len"},
    "dang_chung": {"ten": "Đang chững lại",   "mau": "vang"},
    "on_dinh":    {"ten": "Ổn định",          "mau": "xam"},
    "dang_giam":  {"ten": "Đang giảm",        "mau": "vang"},
    "thoai_trao": {"ten": "Thoái trào",       "mau": "xuong"},
    "chua_du":    {"ten": "Chưa đủ dữ liệu",  "mau": "xam"},
}


# ======================= TIỆN ÍCH =======================
def tien(so) -> str:
    if so >= 1e9:
        return f"{so / 1e9:.1f} tỷ".replace(".", ",")
    if so >= 1e6:
        return f"{so / 1e6:.1f} triệu".replace(".", ",")
    if so >= 1e3:
        return f"{round(so / 1e3):,}".replace(",", ".") + ".000 đ"
    return f"{round(so)} đ"


def so(x) -> str:
    return f"{int(round(x)):,}".replace(",", ".")


def phan_tram(x) -> str:
    return (f"{x:+.0f}%" if abs(x) >= 1 else f"{x:+.1f}%").replace(".", ",")


def trung_binh(ds):
    return sum(ds) / len(ds) if ds else 0.0


# ======================= CHUỖI SỐ BÁN THEO NGÀY =======================
def chuoi_theo_ngay(anh_chup: dict, ngay_cuoi: date) -> dict:
    """{ngày: {mã sản phẩm: số bán trong ngày đó}} cho tối đa 30 ngày gần nhất.
    Hai lần chụp cách nhau nhiều ngày thì chia đều số bán cho các ngày ở giữa."""
    cac_ngay = sorted(n for n in anh_chup if n <= ngay_cuoi)[-(SO_NGAY_BIEU_DO + 1):]
    ket_qua = {}
    for dau, cuoi in zip(cac_ngay[:-1], cac_ngay[1:]):
        so_ngay = (cuoi - dau).days
        a, b = anh_chup[dau], anh_chup[cuoi]
        ban = {ma: max(0, v - a[ma]) / so_ngay for ma, v in b.items() if ma in a}
        for i in range(1, so_ngay + 1):
            ket_qua[dau + timedelta(days=i)] = ban
    return ket_qua


def tinh_giai_doan(chuoi: list, ngay_sale: dict) -> dict:
    """chuoi: [(ngày, số bán)] theo thứ tự thời gian. Bỏ ngày siêu sale trước khi tính."""
    sach = [v for n, v in chuoi if n not in ngay_sale]
    kq = {"ma": "chua_du", "tang_tuan": None, "da_gan_day": None,
          "tb_7_ngay": round(trung_binh(sach[-7:]), 1) if sach else 0}
    if len(sach) < SO_NGAY_TOI_THIEU:
        return kq
    tb7 = trung_binh(sach[-7:])
    tb7_truoc = trung_binh(sach[-14:-7])
    tb3 = trung_binh(sach[-3:])
    tb4_truoc = trung_binh(sach[-7:-3])
    tang_tuan = (tb7 / tb7_truoc - 1) * 100 if tb7_truoc > 0 else (100.0 if tb7 > 0 else 0.0)
    da = (tb3 / tb4_truoc - 1) * 100 if tb4_truoc > 0 else 0.0
    if tang_tuan >= MOI_NOI_TANG_TUAN and da >= 0:
        ma = "moi_noi"
    elif tang_tuan >= DANG_TANG_TANG_TUAN and da >= DA_CHAM_LAI:
        ma = "dang_tang"
    elif tang_tuan >= DANG_TANG_TANG_TUAN:
        ma = "dang_chung"
    elif tang_tuan <= THOAI_TRAO_TUAN:
        ma = "thoai_trao"
    elif tang_tuan < DANG_GIAM_TUAN:
        ma = "dang_giam"
    else:
        ma = "on_dinh"
    kq.update(ma=ma, tang_tuan=round(tang_tuan, 1), da_gan_day=round(da, 1), tb_7_ngay=round(tb7, 1))
    return kq


def tinh_canh_tranh(ban_theo_sp: dict, thong_tin: dict) -> dict:
    """ban_theo_sp: {mã: số bán 7 ngày}. Cộng theo shop."""
    theo_shop = {}
    for ma, sb in ban_theo_sp.items():
        if sb <= 0:
            continue
        shop = thong_tin.get(ma, {}).get("cua_hang") or "Không rõ"
        theo_shop[shop] = theo_shop.get(shop, 0) + sb
    tong = sum(theo_shop.values())
    if not tong:
        return {"muc": None, "so_shop": 0, "top3_phan_tram": None, "shop_dau": []}
    xep = sorted(theo_shop.items(), key=lambda x: x[1], reverse=True)
    top3 = sum(v for _, v in xep[:3]) * 100 / tong
    muc = "cao" if top3 >= CANH_TRANH_CAO else ("thap" if top3 < CANH_TRANH_THAP else "trung_binh")
    return {"muc": muc, "so_shop": len(theo_shop), "top3_phan_tram": round(top3, 1),
            "shop_dau": [{"ten": t, "phan_tram": round(v * 100 / tong, 1)} for t, v in xep[:3]]}


def tinh_khoang_gia(ban_theo_sp: dict, thong_tin: dict) -> dict:
    """Khoảng giá tính theo số lượng bán: một món bán 100 cái được tính nặng gấp 10 món bán 10 cái."""
    cap = sorted((thong_tin[m]["gia"], sb) for m, sb in ban_theo_sp.items()
                 if sb > 0 and thong_tin.get(m, {}).get("gia"))
    tong = sum(sb for _, sb in cap)
    if not tong:
        return None

    def moc(ty_le):
        tich = 0
        for gia, sb in cap:
            tich += sb
            if tich >= tong * ty_le:
                return gia
        return cap[-1][0]
    return {"thap": moc(0.25), "pho_bien": moc(0.5), "cao": moc(0.75)}


def mua_sale_sap_toi(ngay: date, ngay_sale: dict):
    sap = sorted((n, t) for n, t in ngay_sale.items() if ngay < n <= ngay + timedelta(days=SO_NGAY_NHAC_SALE))
    return [{"ngay": n.isoformat(), "ten": t, "con_ngay": (n - ngay).days} for n, t in sap]


# ======================= LỜI KHUYÊN =======================
def loi_khuyen_nhom(ten: str, gd: dict, ct: dict, gia: dict, sale: list, nhom_thay_the: list) -> dict:
    nguoi_ban, tiep_thi = [], []
    ma = gd["ma"]
    muc = ct.get("muc")

    # Theo giai đoạn
    if ma == "chua_du":
        nguoi_ban.append("Chưa đủ 8 ngày số liệu để đánh giá xu hướng. Theo dõi thêm, chưa nên quyết định nhập hàng lớn.")
    elif ma == "moi_noi":
        if muc == "cao":
            nguoi_ban.append(f"Nhóm đang mới nổi (tăng {phan_tram(gd['tang_tuan'])} so với tuần trước) nhưng vài shop lớn đang nắm phần lớn số bán. "
                             "Nếu vào, đừng đối đầu trực tiếp: chọn mẫu mã, màu sắc hoặc khoảng giá khác với các shop đầu.")
        else:
            nguoi_ban.append(f"Cơ hội tốt: nhóm đang mới nổi (tăng {phan_tram(gd['tang_tuan'])} so với tuần trước) và còn chỗ cho shop mới. "
                             "Nên nhập thử số lượng nhỏ ngay để kịp sóng, bán chạy thì nhập thêm.")
        tiep_thi.append("Nên làm video, đăng bài về nhóm này ngay trong tuần, lúc người mua đang tìm nhiều mà chưa nhiều người quảng bá.")
    elif ma == "dang_tang":
        nguoi_ban.append(f"Nhóm đang tăng đều ({phan_tram(gd['tang_tuan'])} so với tuần trước). Có thể nhập, nhưng chia nhỏ đợt nhập và theo dõi thêm 3–5 ngày.")
        tiep_thi.append("Nhóm đang lên đều, phù hợp để quảng bá đều đặn trong 1–2 tuần tới.")
    elif ma == "dang_chung":
        nguoi_ban.append(f"Nhóm vẫn cao hơn tuần trước ({phan_tram(gd['tang_tuan'])}) nhưng 3 ngày gần đây đã chậm lại ({phan_tram(gd['da_gan_day'])}). "
                         "Có thể sắp chạm đỉnh: không nên nhập nhiều thêm, ưu tiên bán hết hàng đang có.")
        tiep_thi.append("Sóng có dấu hiệu chậm lại. Vẫn quảng bá được, nhưng nên chuẩn bị chuyển sang nhóm khác.")
    elif ma == "on_dinh":
        nguoi_ban.append("Nhu cầu đều, không có sóng lớn. Hợp để bán lâu dài; muốn hơn đối thủ thì cạnh tranh bằng giá, dịch vụ và đánh giá tốt.")
        tiep_thi.append("Nhóm ổn định, quảng bá lúc nào cũng có người mua nhưng khó có đột biến.")
    elif ma == "dang_giam":
        nguoi_ban.append(f"Nhóm đang giảm ({phan_tram(gd['tang_tuan'])} so với tuần trước). Hạn chế nhập mới, theo dõi xem có phải giảm tạm thời không.")
        tiep_thi.append("Nhóm đang giảm, nên giảm bớt quảng bá.")
    elif ma == "thoai_trao":
        nguoi_ban.append(f"Nhóm đang thoái trào ({phan_tram(gd['tang_tuan'])} so với tuần trước). Không nên nhập thêm; nếu còn hàng tồn, nên xả sớm khi người mua vẫn còn.")
        tiep_thi.append("Nhóm đang thoái trào, nên chuyển sang nhóm khác.")

    # Theo cạnh tranh
    if muc == "cao":
        nguoi_ban.append(f"Cạnh tranh cao: 3 shop đứng đầu chiếm {str(ct['top3_phan_tram']).replace('.', ',')}% số bán. Người mới vào cần điểm khác biệt rõ ràng.")
    elif muc == "thap":
        nguoi_ban.append(f"Cạnh tranh thấp: số bán chia cho {ct['so_shop']} shop, 3 shop đầu chỉ chiếm {str(ct['top3_phan_tram']).replace('.', ',')}%. Người mới dễ chen chân.")

    # Theo giá
    if gia:
        nguoi_ban.append(f"Khoảng giá bán chạy nhất: {tien(gia['thap'])} – {tien(gia['cao'])}, mức giá bán nhiều nhất khoảng {tien(gia['pho_bien'])}.")

    # Nhóm thay thế khi đang đi xuống
    if ma in ("dang_giam", "thoai_trao", "dang_chung") and nhom_thay_the:
        nguoi_ban.append("Nhóm đang lên có thể chuyển sang: " + ", ".join(nhom_thay_the) + ".")

    # Mùa sale
    for s in sale[:1]:
        if s["con_ngay"] >= 7:
            nguoi_ban.append(f"Còn {s['con_ngay']} ngày tới {s['ten']}: nếu nhập hàng, nên nhập xong trước ít nhất 7 ngày để kịp lên sàn và chạy khuyến mãi.")
        else:
            nguoi_ban.append(f"Chỉ còn {s['con_ngay']} ngày tới {s['ten']}: không kịp nhập hàng mới, tập trung đẩy hàng đang có.")
        tiep_thi.append(f"Chuẩn bị sẵn link và nội dung quảng bá cho {s['ten']} ({s['con_ngay']} ngày nữa).")

    return {"nguoi_ban": nguoi_ban, "tiep_thi": tiep_thi}


def loi_khuyen_san_pham(sp: dict, gd: dict, gia_nhom: dict, phan_tram_trong_nhom, sale: list) -> dict:
    nguoi_ban, tiep_thi = [], []
    ma = gd["ma"]
    if ma == "moi_noi":
        nguoi_ban.append(f"Sản phẩm đang mới nổi (tăng {phan_tram(gd['tang_tuan'])} so với tuần trước). Nên tìm nguồn hàng tương tự hoặc cùng loại ngay.")
        tiep_thi.append("Đang mới nổi: nên quảng bá ngay, càng sớm càng có lợi.")
    elif ma == "dang_tang":
        nguoi_ban.append(f"Sản phẩm đang bán tăng đều ({phan_tram(gd['tang_tuan'])} so với tuần trước). Có thể nhập hàng cùng loại, theo dõi thêm vài ngày.")
        tiep_thi.append("Đang tăng đều, quảng bá được trong 1–2 tuần tới.")
    elif ma == "dang_chung":
        nguoi_ban.append("Sản phẩm vẫn cao hơn tuần trước nhưng mấy ngày gần đây chậm lại, có thể sắp đỉnh. Không nên nhập nhiều.")
        tiep_thi.append("Sóng đang chậm lại, quảng bá tranh thủ trong vài ngày tới.")
    elif ma == "on_dinh":
        nguoi_ban.append("Bán đều, không đột biến. Hợp để bán lâu dài nếu có nguồn giá tốt.")
        tiep_thi.append("Bán đều, quảng bá lúc nào cũng được.")
    elif ma in ("dang_giam", "thoai_trao"):
        nguoi_ban.append(f"Sản phẩm đang giảm ({phan_tram(gd['tang_tuan'])} so với tuần trước). Không nên nhập theo.")
        tiep_thi.append("Đang giảm, nên ưu tiên sản phẩm khác.")
    else:
        nguoi_ban.append("Chưa đủ 8 ngày số liệu để đánh giá xu hướng của sản phẩm này.")

    if gia_nhom and sp.get("gia"):
        if sp["gia"] < gia_nhom["thap"]:
            nguoi_ban.append(f"Giá {tien(sp['gia'])} thấp hơn khoảng giá bán chạy của nhóm ({tien(gia_nhom['thap'])} – {tien(gia_nhom['cao'])}): đang thắng nhờ giá rẻ.")
        elif sp["gia"] > gia_nhom["cao"]:
            nguoi_ban.append(f"Giá {tien(sp['gia'])} cao hơn khoảng giá bán chạy của nhóm ({tien(gia_nhom['thap'])} – {tien(gia_nhom['cao'])}): bán chạy nhờ chất lượng hoặc thương hiệu, không nhờ giá.")
        else:
            nguoi_ban.append(f"Giá {tien(sp['gia'])} nằm trong khoảng giá bán chạy của nhóm ({tien(gia_nhom['thap'])} – {tien(gia_nhom['cao'])}).")
    if phan_tram_trong_nhom is not None and phan_tram_trong_nhom >= 5:
        nguoi_ban.append(f"Riêng sản phẩm này chiếm {str(phan_tram_trong_nhom).replace('.', ',')}% số bán của cả nhóm trong 7 ngày qua.")
    if sp.get("danh_gia"):
        if sp["danh_gia"] >= 4.8:
            nguoi_ban.append(f"Đánh giá {str(sp['danh_gia']).replace('.', ',')} sao, rất cao: nếu bán hàng cùng loại phải đảm bảo chất lượng tương đương.")
        elif sp["danh_gia"] < 4.5:
            nguoi_ban.append(f"Đánh giá chỉ {str(sp['danh_gia']).replace('.', ',')} sao: người mua có phàn nàn. Đây là cơ hội cho shop làm chất lượng tốt hơn.")
    if sp.get("hoa_hong"):
        muc = "cao" if sp["hoa_hong"] >= 8 else ("khá" if sp["hoa_hong"] >= 4 else "thấp")
        tiep_thi.append(f"Hoa hồng {str(sp['hoa_hong']).replace('.', ',')}%, mức {muc}.")
    for s in sale[:1]:
        tiep_thi.append(f"Còn {s['con_ngay']} ngày tới {s['ten']}: thường bán gấp nhiều lần ngày thường, nên chuẩn bị link sớm.")
    return {"nguoi_ban": nguoi_ban, "tiep_thi": tiep_thi}


def tinh_gian_hang_uy_tin(ban_theo_sp: dict, thong_tin: dict) -> list:
    """Gom số bán 7 ngày theo gian hàng, lọc gian hàng uy tín, xếp theo điểm uy tín.
    Điểm uy tín = số bán × hệ số loại shop × (điểm đánh giá / 5) mũ 4.
    Hệ số loại shop: Shopee Mall 1,6; Shop Yêu thích+ 1,4; Shop Yêu thích 1,25; shop thường 1."""
    gom = {}
    for ma, sb in ban_theo_sp.items():
        tt = thong_tin.get(ma, {})
        ten = tt.get("cua_hang")
        if sb <= 0 or not ten:
            continue
        g = gom.setdefault(tt.get("ma_shop") or ten, {"ten": ten, "ma_shop": tt.get("ma_shop") or "", "loai": set(),
                                                      "so_ban": 0, "tong_sao": 0.0, "so_sp": 0, "sp_dau": None})
        g["so_ban"] += sb
        g["so_sp"] += 1
        g["tong_sao"] += sb * (tt.get("danh_gia") or 0)
        g["loai"].update(tt.get("loai_shop") or [])
        if not g["sp_dau"] or sb > g["sp_dau"][0]:
            g["sp_dau"] = (sb, ma)
    he_so = {"mall": 1.6, "yeu_thich_plus": 1.4, "yeu_thich": 1.25}
    ket_qua = []
    for g in gom.values():
        sao = g["tong_sao"] / g["so_ban"] if g["so_ban"] else 0
        la_mall = "mall" in g["loai"]
        dat = sao >= (DANH_GIA_TOI_THIEU_MALL if la_mall else DANH_GIA_TOI_THIEU) and g["so_ban"] >= SO_BAN_TOI_THIEU_7_NGAY
        if not dat:
            continue
        hs = max([he_so.get(x, 1.0) for x in g["loai"]] + [1.0])
        sp_dau = thong_tin.get(g["sp_dau"][1], {})
        ket_qua.append({
            "ten": g["ten"], "ma_shop": g["ma_shop"], "loai": sorted(g["loai"]),
            "so_ban_7_ngay": round(g["so_ban"]), "danh_gia": round(sao, 2), "so_sp_ban_chay": g["so_sp"],
            "diem": round(g["so_ban"] * hs * (sao / 5) ** 4, 1),
            "sp_noi_bat": sp_dau.get("ten", ""), "anh": sp_dau.get("anh", ""),
            "lien_ket_san_pham": sp_dau.get("duong_dan", ""),
        })
    ket_qua.sort(key=lambda x: x["diem"], reverse=True)
    return ket_qua[:SO_GIAN_HANG_MOI_NGANH]


def ket_luan_ngan(gd: dict, ct: dict) -> str:
    """Một câu kết luận nhanh cho từng loại hàng trong nhóm."""
    ma, muc = gd["ma"], ct.get("muc")
    if ma == "chua_du":
        return "Chưa đủ số liệu."
    if ma == "moi_noi":
        return "Nên nhập thử ngay." if muc != "cao" else "Đang lên nhưng vài shop lớn nắm, cần khác biệt."
    if ma == "dang_tang":
        return "Có thể nhập, chia nhỏ đợt." if muc != "cao" else "Đang tăng, nhưng cạnh tranh cao."
    if ma == "dang_chung":
        return "Sắp đỉnh, không nhập thêm nhiều."
    if ma == "on_dinh":
        return "Bán đều, hợp bán lâu dài." if muc != "cao" else "Bán đều, nhưng vài shop lớn nắm."
    if ma == "dang_giam":
        return "Hạn chế nhập mới."
    return "Không nên nhập, xả tồn sớm."


# ======================= TỔNG HỢP =======================
def phan_tich_toan_bo(ngay: date, anh_chup: dict, thong_tin: dict, ngay_sale: dict, ma_can_phan_tich: set) -> dict:
    theo_ngay = chuoi_theo_ngay(anh_chup, ngay)
    cac_ngay = sorted(theo_ngay)
    sale = mua_sale_sap_toi(ngay, ngay_sale)

    # Số bán 7 ngày gần nhất của từng sản phẩm (để tính cạnh tranh, khoảng giá)
    ban_7_ngay = {}
    for n in cac_ngay[-7:]:
        for ma, v in theo_ngay[n].items():
            ban_7_ngay[ma] = ban_7_ngay.get(ma, 0) + v

    # Chuỗi theo nhóm
    chuoi_nhom, ban_7_theo_nhom = {}, {}
    for n in cac_ngay:
        tong = {}
        for ma, v in theo_ngay[n].items():
            nhom = thong_tin.get(ma, {}).get("nhom")
            if nhom:
                tong[nhom] = tong.get(nhom, 0) + v
        for nhom, v in tong.items():
            chuoi_nhom.setdefault(nhom, {})[n] = v
    for ma, v in ban_7_ngay.items():
        nhom = thong_tin.get(ma, {}).get("nhom")
        if nhom:
            ban_7_theo_nhom.setdefault(nhom, {})[ma] = v

    def dang_bieu_do(du_lieu: dict):
        return [{"ngay": n.isoformat(), "so_ban": round(du_lieu.get(n, 0)), "sale": n in ngay_sale} for n in cac_ngay]

    # Phân tích từng nhóm
    nhom_kq = {}
    for nhom in sorted(chuoi_nhom):
        chuoi = [(n, chuoi_nhom[nhom].get(n, 0)) for n in cac_ngay]
        ban7 = ban_7_theo_nhom.get(nhom, {})
        nhom_kq[nhom] = {
            "giai_doan": tinh_giai_doan(chuoi, ngay_sale),
            "canh_tranh": tinh_canh_tranh(ban7, thong_tin),
            "khoang_gia": tinh_khoang_gia(ban7, thong_tin),
            "bieu_do": dang_bieu_do(chuoi_nhom[nhom]),
            "ban_7_ngay": round(sum(ban7.values())),
            "gian_hang": tinh_gian_hang_uy_tin(ban7, thong_tin),
        }
    # Từng loại hàng (theo từ khóa) trong mỗi nhóm
    chuoi_loai, ban_7_theo_loai = {}, {}
    for n in cac_ngay:
        tong = {}
        for ma, v in theo_ngay[n].items():
            tt = thong_tin.get(ma, {})
            if tt.get("nhom") and tt.get("tu_khoa"):
                k = (tt["nhom"], tt["tu_khoa"])
                tong[k] = tong.get(k, 0) + v
        for k, v in tong.items():
            chuoi_loai.setdefault(k, {})[n] = v
    for ma, v in ban_7_ngay.items():
        tt = thong_tin.get(ma, {})
        if tt.get("nhom") and tt.get("tu_khoa"):
            ban_7_theo_loai.setdefault((tt["nhom"], tt["tu_khoa"]), {})[ma] = v
    for (nhom, tu_khoa), du_lieu in chuoi_loai.items():
        if nhom not in nhom_kq:
            continue
        chuoi = [(n, du_lieu.get(n, 0)) for n in cac_ngay]
        ban7 = ban_7_theo_loai.get((nhom, tu_khoa), {})
        gd = tinh_giai_doan(chuoi, ngay_sale)
        ct = tinh_canh_tranh(ban7, thong_tin)
        nhom_kq[nhom].setdefault("theo_loai", []).append({
            "ten": tu_khoa, "giai_doan": {**gd, **GIAI_DOAN[gd["ma"]]}, "canh_tranh": ct,
            "khoang_gia": tinh_khoang_gia(ban7, thong_tin), "ban_7_ngay": round(sum(ban7.values())),
            "ket_luan": ket_luan_ngan(gd, ct),
        })
    for v in nhom_kq.values():
        v.setdefault("theo_loai", []).sort(key=lambda x: x["ban_7_ngay"], reverse=True)

    # Nhóm thay thế = các nhóm mới nổi / đang tăng mạnh nhất
    dang_len = sorted((k for k, v in nhom_kq.items() if v["giai_doan"]["ma"] in ("moi_noi", "dang_tang")),
                      key=lambda k: nhom_kq[k]["giai_doan"]["tang_tuan"] or 0, reverse=True)
    for nhom, v in nhom_kq.items():
        thay_the = [k for k in dang_len if k != nhom][:3]
        v["loi_khuyen"] = loi_khuyen_nhom(nhom, v["giai_doan"], v["canh_tranh"], v["khoang_gia"], sale, thay_the)
        v["giai_doan"].update(GIAI_DOAN[v["giai_doan"]["ma"]])

    # Phân tích từng sản phẩm (chỉ những sản phẩm có trên trang, cho nhẹ file)
    sp_kq = {}
    for ma in ma_can_phan_tich:
        chuoi_sp = {n: theo_ngay[n].get(ma, 0) for n in cac_ngay if ma in theo_ngay[n]}
        if not chuoi_sp:
            continue
        chuoi = [(n, chuoi_sp.get(n, 0)) for n in cac_ngay if n in chuoi_sp]
        tt = thong_tin.get(ma, {})
        nhom = tt.get("nhom")
        gd = tinh_giai_doan(chuoi, ngay_sale)
        tong_nhom = nhom_kq.get(nhom, {}).get("ban_7_ngay") or 0
        pt = round(ban_7_ngay.get(ma, 0) * 100 / tong_nhom, 1) if tong_nhom else None
        sp_tom_tat = {"gia": tt.get("gia"), "danh_gia": tt.get("danh_gia"), "hoa_hong": tt.get("hoa_hong")}
        sp_kq[ma] = {
            "giai_doan": {**gd, **GIAI_DOAN[gd["ma"]]},
            "bieu_do": dang_bieu_do(chuoi_sp),
            "ban_7_ngay": round(ban_7_ngay.get(ma, 0)),
            "phan_tram_trong_nhom": pt,
            "loi_khuyen": loi_khuyen_san_pham(sp_tom_tat, gd, nhom_kq.get(nhom, {}).get("khoang_gia"), pt, sale),
        }
    return {"nhom": nhom_kq, "san_pham": sp_kq, "sale_sap_toi": sale}
