# Hướng dẫn cài đặt – Nhóm hàng bán chạy Shopee

## Trang này làm gì
- Mỗi sáng 6 giờ 47, máy của GitHub tự chạy, lấy sản phẩm bán chạy nhất của 20 nhóm hàng (80 từ khóa, mỗi từ khóa 100 sản phẩm) từ Shopee.
- Xếp hạng nhóm hàng bán chạy nhất **hôm nay, 7 ngày qua, 30 ngày qua**, theo số lượng bán hoặc theo doanh thu ước tính.
- So sánh với kỳ trước để biết nhóm nào đang tăng, nhóm nào đang giảm.
- Gửi bảng xếp hạng về Telegram.

## Lưu ý quan trọng về số liệu
Shopee chỉ công bố "tổng số đã bán từ trước tới nay" của mỗi sản phẩm. Chương trình phải chụp con số này mỗi ngày rồi lấy hiệu số. Vì vậy:
- **Ngày đầu tiên:** chưa có số bán, chỉ mới chụp lần đầu.
- **Từ ngày thứ 2:** có số bán trong ngày.
- **Đủ 7 ngày:** có số bán cả tuần. **Đủ 30 ngày:** có số bán cả tháng.
- Muốn có phần "so với kỳ trước": ngày cần 3 ngày dữ liệu, tuần cần 15 ngày, tháng cần 61 ngày.
- Trước khi đủ ngày, trang hiển thị dòng thông báo màu vàng, cho biết đang tính trên bao nhiêu ngày.

## Bước 1 – Đăng ký tiếp thị liên kết Shopee
1. Vào https://affiliate.shopee.vn, đăng ký tài khoản tiếp thị liên kết bằng tài khoản Shopee của Tú, chờ duyệt.
2. Sau khi được duyệt, vào mục **Open API** (cổng dữ liệu mở), tạo ứng dụng.
3. Ghi lại **AppID** (mã ứng dụng) và **Secret** (khóa bí mật). Không gửi hai mã này cho ai.

## Bước 2 – Đưa mã nguồn lên GitHub
1. Tạo kho mới trên GitHub, ví dụ tên `shopee-ban-chay`.
2. Tải toàn bộ các file trong thư mục này lên kho. Phải giữ nguyên thư mục `.github/workflows/` và `du_lieu/anh_chup/`.
3. Vào **Settings → Pages**, phần **Source** chọn `Deploy from a branch`, nhánh `main`, thư mục `/ (root)`, bấm **Save**.
   Trang sẽ có địa chỉ `https://kingtip518.github.io/shopee-ban-chay/`.

## Bước 3 – Khai báo mã bí mật
Vào **Settings → Secrets and variables → Actions → New repository secret**, tạo lần lượt:

| Tên | Giá trị |
|---|---|
| `SHOPEE_APP_ID` | AppID ở bước 1 |
| `SHOPEE_SECRET` | Secret ở bước 1 |
| `TELEGRAM_BOT_TOKEN` | mã con bot Telegram (dùng lại bot của các trang khác cũng được) |
| `TELEGRAM_CHAT_ID` | mã cuộc trò chuyện nhận tin |

Không muốn nhận Telegram thì bỏ qua hai dòng cuối.

## Bước 4 – Chạy lần đầu
1. Vào mục **Actions** của kho, chọn **Cập nhật bán chạy Shopee hằng ngày**, bấm **Run workflow**.
2. Chờ khoảng 3–5 phút. Dấu tích xanh là chạy được.
3. Nếu có dấu X đỏ: bấm vào, mở bước **Lấy dữ liệu và tính xếp hạng**, chụp màn hình phần chữ báo lỗi gửi lại để sửa.

## Thêm, bớt nhóm hàng
Sửa file `nhom_hang.json`. Mỗi nhóm có tên và danh sách từ khóa tìm kiếm trên Shopee. Nên giữ số từ khóa các nhóm gần bằng nhau, để so sánh giữa các nhóm được công bằng.

## Các file
| File | Tác dụng |
|---|---|
| `index.html` | Trang web hiển thị |
| `lay_du_lieu.py` | Chương trình lấy dữ liệu, tính xếp hạng, gửi Telegram |
| `nhom_hang.json` | Danh sách nhóm hàng và từ khóa |
| `.github/workflows/cap_nhat_hang_ngay.yml` | Lịch chạy tự động mỗi sáng |
| `du_lieu/` | Nơi lưu ảnh chụp hằng ngày và bảng xếp hạng (máy tự ghi, không cần sửa) |
