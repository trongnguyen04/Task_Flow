# Task Flow

Hệ thống quản lý và ưu tiên công việc trong môi trường đa dự án.

## Công nghệ

- Backend: Flask
- Frontend: Jinja2, HTML, CSS, JavaScript
- Database: MySQL
- ORM: SQLAlchemy
- Authentication: đăng nhập bằng email và session
- Authorization: phân quyền theo role Admin / Member

## Chạy local

1. Tạo database MySQL:

```sql
CREATE DATABASE taskdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Tạo file `.env` từ `.env.example`, sau đó sửa thông tin kết nối MySQL:

```text
DATABASE_URL=mysql+mysqlconnector://root:your_password@localhost:3306/taskdb?charset=utf8mb4
```

3. Cài thư viện:

```bash
python -m pip install -r requirements.txt
```

4. Tạo bảng và seed dữ liệu demo:

```bash
flask --app run.py init-db
flask --app run.py seed-db
```

5. Chạy ứng dụng:

```bash
python run.py
```

Ứng dụng chạy tại:

```text
http://127.0.0.1:5001
```

Email demo:

- `admin@taskflow.local`
- `member@taskflow.local`

## Phân quyền

- Admin: quản lý người dùng, dự án, task, phân công công việc, gửi thông báo khi giao task, thiết lập mức ưu tiên và xem dashboard tổng.
- Member: vào màn hình “Việc của tôi”, chỉ xem task được giao, xem task theo thứ tự ưu tiên và cập nhật trạng thái `Todo -> Doing -> Done`.

## Luồng Member

- Sau khi đăng nhập, Member được chuyển thẳng đến “Việc của tôi”.
- Danh sách công việc được sắp xếp theo ưu tiên: `Critical -> High -> Medium -> Low`.
- Member chỉ nhìn thấy dự án/task có liên quan đến mình.
- Member có thể cập nhật trạng thái task bằng dropdown trong bảng hoặc kéo thả trên màn hình Kanban.
- Khi Admin giao task cho Member, hệ thống tạo thông báo trong mục “Thông báo”.
- Member có thể xem thông báo chưa đọc và đánh dấu đã đọc.
