from datetime import date, timedelta

import click
from sqlalchemy import or_, text
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import (
    PRIORITIES,
    STATUSES,
    Notification,
    Project,
    ProjectMember,
    Task,
    TaskHistory,
    User,
)
from .services import notify_assignment


LARGE_DATA_PASSWORD = "Test123!"
LARGE_DATASET_MARKER = "Generated dataset tag"
TASKS_PER_PREFERRED_ASSIGNEE = 100
PREFERRED_ASSIGNEE_EMAILS = (
    "member@taskflow.local",
    "huynhtrongnguyen122@gmail.com",
)
PROJECT_BLUEPRINTS = (
    ("Cổng Tiếp nhận và Phân luồng Yêu cầu", "Tiếp nhận yêu cầu từ nhiều kênh và tự động chuyển đến đúng bộ phận xử lý."),
    ("Hệ thống Theo dõi Đơn hàng Đa Kênh", "Hợp nhất trạng thái đơn hàng từ cửa hàng, website và đối tác phân phối."),
    ("Trung tâm Điều phối Giao nhận", "Lập tuyến, phân tài xế và giám sát tiến độ giao nhận theo thời gian thực."),
    ("Nền tảng Dự báo Nhu cầu Kho", "Dự báo nhu cầu tồn kho theo mùa vụ, khu vực và nhóm sản phẩm."),
    ("Cổng Đối soát Thanh toán", "Đối chiếu giao dịch, phát hiện chênh lệch và hỗ trợ xử lý hoàn tiền."),
    ("Hệ thống Quản lý Hợp đồng Điện tử", "Quản lý vòng đời hợp đồng từ soạn thảo, phê duyệt đến ký số và gia hạn."),
    ("Nền tảng Chăm sóc Khách hàng 360", "Tổng hợp lịch sử tương tác để hỗ trợ chăm sóc khách hàng theo ngữ cảnh."),
    ("Trung tâm Giám sát Chất lượng Dịch vụ", "Theo dõi chỉ số chất lượng và cảnh báo khi dịch vụ không đạt cam kết."),
    ("Cổng Đăng ký Nhà cung cấp", "Chuẩn hóa quy trình đăng ký, đánh giá và phê duyệt nhà cung cấp mới."),
    ("Hệ thống Quản trị Tài sản Nội bộ", "Theo dõi cấp phát, điều chuyển, kiểm kê và thanh lý tài sản doanh nghiệp."),
    ("Nền tảng Tuyển dụng và Hội nhập Nhân sự", "Quản lý ứng viên và kế hoạch hội nhập cho nhân viên mới."),
    ("Cổng Đào tạo Năng lực Trực tuyến", "Phân phối khóa học và đo lường mức độ hoàn thành theo khung năng lực."),
    ("Hệ thống Chấm công và Lịch làm việc", "Quản lý ca làm, chấm công và các trường hợp điều chỉnh thời gian."),
    ("Trung tâm Phân tích Hiệu suất Kinh doanh", "Tổng hợp chỉ số doanh thu, chi phí và hiệu suất theo đơn vị."),
    ("Nền tảng Quản lý Ngân sách Phòng ban", "Lập ngân sách, kiểm soát hạn mức và theo dõi mức sử dụng thực tế."),
    ("Cổng Phê duyệt Chi phí Công tác", "Số hóa đề nghị công tác, tạm ứng, hóa đơn và quyết toán chi phí."),
    ("Hệ thống Quản lý Danh mục Sản phẩm", "Quản lý thông tin, thuộc tính và vòng đời của từng danh mục sản phẩm."),
    ("Nền tảng Khuyến mãi Cá nhân hóa", "Thiết kế ưu đãi theo phân khúc và đo lường hiệu quả từng chiến dịch."),
    ("Trung tâm Phân tích Hành vi Người dùng", "Phân tích hành trình, điểm rời bỏ và xu hướng sử dụng sản phẩm."),
    ("Cổng Hỗ trợ Kỹ thuật Tự phục vụ", "Cung cấp tri thức, hướng dẫn và quy trình tự xử lý sự cố phổ biến."),
    ("Hệ thống Giám sát Hạ tầng Thời gian thực", "Thu thập chỉ số hạ tầng và cảnh báo sớm các dấu hiệu bất thường."),
    ("Nền tảng Quản lý Sự cố và Thay đổi", "Kiểm soát sự cố, yêu cầu thay đổi và lịch triển khai hệ thống."),
    ("Cổng Kiểm soát Truy cập Tập trung", "Quản lý quyền truy cập theo vai trò và ghi nhận lịch sử xác thực."),
    ("Hệ thống Sao lưu và Khôi phục Dữ liệu", "Điều phối lịch sao lưu và kiểm chứng khả năng khôi phục định kỳ."),
    ("Trung tâm Cảnh báo An toàn Thông tin", "Tập trung cảnh báo bảo mật và hỗ trợ phân loại mức độ ảnh hưởng."),
    ("Nền tảng Tích hợp Dữ liệu Doanh nghiệp", "Đồng bộ dữ liệu giữa các hệ thống qua luồng tích hợp có kiểm soát."),
    ("Cổng Tra cứu Báo cáo Điều hành", "Cung cấp báo cáo quản trị theo vai trò với dữ liệu được cập nhật liên tục."),
    ("Hệ thống Quản lý Chỉ tiêu Chiến lược", "Theo dõi mục tiêu, kết quả then chốt và tiến độ thực hiện chiến lược."),
    ("Nền tảng Lập kế hoạch Nguồn lực", "Cân đối nhân lực và năng lực thực hiện theo nhu cầu từng giai đoạn."),
    ("Trung tâm Điều phối Dự án Liên phòng ban", "Quản lý phụ thuộc và phối hợp tiến độ giữa nhiều đơn vị tham gia."),
    ("Cổng Quản lý Hồ sơ Pháp lý", "Lưu trữ hồ sơ pháp lý và theo dõi thời hạn hiệu lực của tài liệu."),
    ("Hệ thống Theo dõi Tuân thủ Nội bộ", "Ghi nhận yêu cầu tuân thủ, bằng chứng kiểm soát và kế hoạch khắc phục."),
    ("Nền tảng Quản lý Rủi ro Doanh nghiệp", "Đánh giá xác suất, tác động và biện pháp ứng phó cho từng rủi ro."),
    ("Cổng Tiếp nhận Phản ánh Hiện trường", "Tiếp nhận phản ánh có vị trí, hình ảnh và trạng thái xử lý thực địa."),
    ("Hệ thống Bảo trì Thiết bị Chủ động", "Lập lịch bảo trì dựa trên tình trạng và lịch sử vận hành thiết bị."),
    ("Nền tảng Theo dõi Năng lượng và Phát thải", "Đo lường tiêu thụ năng lượng và lượng phát thải theo cơ sở."),
    ("Trung tâm Quản lý Dữ liệu Chủ", "Chuẩn hóa dữ liệu dùng chung và kiểm soát chất lượng bản ghi chủ."),
    ("Cổng Chia sẻ Tài liệu An toàn", "Chia sẻ tài liệu theo phạm vi truy cập, thời hạn và chính sách bảo mật."),
    ("Hệ thống Quản lý Phiên bản Sản phẩm", "Theo dõi yêu cầu, phạm vi và lịch phát hành của từng phiên bản."),
    ("Nền tảng Kiểm thử Tự động Đa Môi trường", "Điều phối bộ kiểm thử và so sánh kết quả giữa các môi trường."),
    ("Cổng Quản lý Đối tác Phân phối", "Theo dõi hồ sơ, doanh số và cam kết hợp tác của mạng lưới phân phối."),
    ("Hệ thống Dự báo Doanh thu Theo Khu vực", "Dự báo doanh thu theo địa bàn và nhận diện sớm khoảng cách mục tiêu."),
    ("Nền tảng Quản lý Chương trình Khách hàng", "Quản lý hạng thành viên, quyền lợi và lịch sử tích lũy điểm."),
    ("Trung tâm Điều hành Chuỗi Cung ứng", "Theo dõi nguồn cung, tồn kho, vận chuyển và nguy cơ gián đoạn."),
    ("Cổng Đăng ký và Theo dõi Bảo hành", "Tiếp nhận bảo hành và minh bạch tiến độ sửa chữa cho khách hàng."),
    ("Hệ thống Quản lý Lịch Hẹn Dịch vụ", "Điều phối lịch hẹn, năng lực phục vụ và nhắc lịch tự động."),
    ("Nền tảng Khảo sát Trải nghiệm Khách hàng", "Thu thập phản hồi và phân tích mức độ hài lòng theo điểm chạm."),
    ("Trung tâm Điều phối Nội dung Số", "Quản lý lịch biên tập, phê duyệt và xuất bản nội dung đa kênh."),
    ("Cổng Quản lý Yêu cầu Mua sắm", "Số hóa đề nghị mua sắm, lấy báo giá và theo dõi tiến độ cung ứng."),
    ("Hệ thống Theo dõi Cam kết Dịch vụ", "Quản lý SLA, thời gian phản hồi và nguyên nhân vi phạm cam kết."),
)

TASK_ACTIONS = (
    "Phân tích",
    "Thiết kế",
    "Xây dựng",
    "Kiểm thử",
    "Tối ưu",
    "Tích hợp",
    "Rà soát",
    "Chuẩn hóa",
    "Tự động hóa",
    "Giám sát",
)
TASK_SUBJECTS = (
    "quy trình đăng nhập",
    "bảng điều khiển",
    "API dự án",
    "luồng phân công",
    "hệ thống thông báo",
    "báo cáo tiến độ",
    "quản lý thành viên",
    "bộ lọc công việc",
    "dữ liệu Kanban",
    "cơ chế phân quyền",
)
TASK_CONTEXTS = (
    "cho nhóm vận hành",
    "trên thiết bị di động",
    "trong giờ cao điểm",
    "cho bản phát hành tháng",
    "theo phản hồi người dùng",
    "với dữ liệu quy mô lớn",
    "cho môi trường thử nghiệm",
    "theo tiêu chuẩn bảo mật",
    "trong quy trình nội bộ",
    "cho khách hàng doanh nghiệp",
)
TASK_FOCUSES = (
    "tính bảo mật",
    "hiệu năng xử lý",
    "khả năng sử dụng",
    "độ chính xác dữ liệu",
    "khả năng mở rộng",
    "tính ổn định",
    "khả năng quan sát",
    "mức độ tự động hóa",
    "tính tương thích",
    "khả năng bảo trì",
)
TASK_PHASES = (
    "giai đoạn khảo sát",
    "giai đoạn thử nghiệm",
    "giai đoạn triển khai",
    "giai đoạn vận hành",
    "giai đoạn cải tiến",
)
TASK_OUTCOMES = (
    "rút ngắn thời gian xử lý",
    "giảm thao tác thủ công",
    "tăng độ ổn định",
    "cải thiện khả năng theo dõi",
    "bảo đảm dữ liệu nhất quán",
    "nâng cao trải nghiệm sử dụng",
    "giảm rủi ro vận hành",
    "tăng tốc độ phản hồi",
    "đơn giản hóa bảo trì",
    "hỗ trợ mở rộng hệ thống",
)
TASK_DELIVERABLES = (
    "tài liệu phân tích và tiêu chí nghiệm thu",
    "bản thiết kế đã được rà soát",
    "mã nguồn kèm kiểm thử tự động",
    "báo cáo kết quả và danh sách vấn đề",
    "cấu hình triển khai có hướng dẫn",
    "bộ dữ liệu kiểm thử đại diện",
    "dashboard theo dõi chỉ số chính",
    "quy trình vận hành được cập nhật",
    "API có tài liệu và ví dụ sử dụng",
    "kế hoạch cải tiến cho vòng tiếp theo",
)
TASK_CONSTRAINTS = (
    "không làm gián đoạn dịch vụ hiện tại",
    "hoàn thành trong khung thời gian đã thống nhất",
    "có số liệu trước và sau để đối chiếu",
    "được kiểm thử trên nhiều vai trò người dùng",
    "tuân thủ quy ước mã nguồn của dự án",
    "có phương án quay lui khi triển khai",
    "bảo đảm tương thích với dữ liệu cũ",
    "có hướng dẫn vận hành rõ ràng",
    "được một thành viên khác rà soát",
    "ghi nhận đầy đủ rủi ro và giả định",
)


def register_commands(app):
    @app.cli.command("check-db")
    def check_db():
        try:
            db.session.execute(text("SELECT 1"))
            click.echo("Database connection successful.")
        except SQLAlchemyError as exc:
            click.echo("Database connection failed.")
            click.echo(str(exc))

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("reset-db")
    def reset_db():
        db.drop_all()
        db.create_all()
        click.echo("Database reset complete (all data cleared).")

    @app.cli.command("seed-db")
    def seed_db():
        db.create_all()

        demo_users = [
            ("Admin", "admin@taskflow.local", "Admin", "admin123"),
            ("Member", "member@taskflow.local", "Member", "member123"),
        ]

        created_users = {}
        for full_name, email, role, password in demo_users:
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(full_name=full_name, email=email, role=role)
                user.set_password(password)
                db.session.add(user)
            else:
                user.full_name = full_name
                user.role = role
                user.is_active = True
                if not user.password_hash:
                    user.set_password(password)
            created_users[email] = user

        db.session.flush()

        project = Project.query.filter_by(name="Task Flow Demo").first()
        if not project:
            project = Project(
                name="Task Flow Demo",
                description="Dự án mẫu cho hệ thống quản lý công việc đa dự án.",
                status="Active",
            )
            db.session.add(project)
            db.session.flush()

        for email in created_users:
            exists = ProjectMember.query.filter_by(
                project_id=project.id,
                user_id=created_users[email].id,
            ).first()
            if not exists:
                db.session.add(
                    ProjectMember(
                        project_id=project.id,
                        user_id=created_users[email].id,
                        role_in_project=created_users[email].role,
                    )
                )

        _ensure_task(
            project,
            title="Hoàn thiện màn hình danh sách công việc",
            description="Kết nối giao diện với dữ liệu mẫu và bộ lọc.",
            priority="High",
            status="Doing",
            assignee=created_users["member@taskflow.local"],
            creator=created_users["admin@taskflow.local"],
        )
        _ensure_task(
            project,
            title="Kiểm tra flow đăng nhập bằng email",
            description="Đảm bảo người dùng có email hợp lệ đăng nhập được.",
            priority="Medium",
            status="Todo",
            assignee=created_users["member@taskflow.local"],
            creator=created_users["admin@taskflow.local"],
        )

        db.session.commit()
        click.echo("Demo data seeded.")
        click.echo("  admin@taskflow.local  /  admin123")
        click.echo("  member@taskflow.local /  member123")

    @app.cli.command("seed-large-db")
    @click.option("--users", default=100, show_default=True, type=click.IntRange(min=2))
    @click.option("--projects", default=50, show_default=True, type=click.IntRange(min=1))
    @click.option("--tasks-per-project", default=1000, show_default=True, type=click.IntRange(min=1))
    @click.option("--members-per-project", default=8, show_default=True, type=click.IntRange(min=1))
    @click.option("--tag", default="load", show_default=True)
    @click.option("--replace", is_flag=True, help="Delete existing generated data with this tag before creating it again.")
    def seed_large_db(users, projects, tasks_per_project, members_per_project, tag, replace):
        """Create a large, relationship-safe dataset for performance testing."""
        tag = _clean_tag(tag)
        db.create_all()

        existing_projects = _large_project_query(tag).count()
        existing_users = User.query.filter(User.email.like(f"{tag}_%@taskflow.local")).count()
        if (existing_projects or existing_users) and not replace:
            click.echo(
                f"Generated data with tag '{tag}' already exists "
                f"({existing_users} users, {existing_projects} projects)."
            )
            click.echo("Run again with --replace to recreate this generated dataset.")
            return

        if replace:
            _delete_large_dataset(tag)

        admin = User(
            full_name=f"{tag.upper()} Admin",
            email=f"{tag}_admin@taskflow.local",
            role="Admin",
            is_active=True,
        )
        admin.set_password(LARGE_DATA_PASSWORD)
        db.session.add(admin)

        member_count = users - 1
        members = []
        for i in range(1, member_count + 1):
            member = User(
                full_name=f"{tag.upper()} Member {i:03d}",
                email=f"{tag}_user_{i:03d}@taskflow.local",
                role="Member",
                is_active=True,
            )
            member.set_password(LARGE_DATA_PASSWORD)
            members.append(member)

        db.session.add_all(members)
        db.session.flush()

        start = date.today()
        generated_projects = []
        for i in range(1, projects + 1):
            project = Project(
                name=_large_project_name(i),
                description=_large_project_description(tag, i),
                status="Active" if i % 5 else "Paused",
                start_date=start - timedelta(days=i % 30),
                end_date=start + timedelta(days=30 + (i % 90)),
            )
            generated_projects.append(project)

        db.session.add_all(generated_projects)
        db.session.flush()

        assignees_by_email = {
            user.email: user
            for user in User.query.filter(User.email.in_(PREFERRED_ASSIGNEE_EMAILS), User.is_active.is_(True)).all()
        }
        preferred_assignees = [
            assignees_by_email[email]
            for email in PREFERRED_ASSIGNEE_EMAILS
            if email in assignees_by_email
        ]

        membership_rows = []
        for index, project in enumerate(generated_projects):
            selected_members = _members_for_project(members, index, members_per_project)
            membership_rows.append(
                ProjectMember(
                    project_id=project.id,
                    user_id=admin.id,
                    role_in_project="Admin",
                )
            )
            for member in selected_members:
                membership_rows.append(
                    ProjectMember(
                        project_id=project.id,
                        user_id=member.id,
                        role_in_project="Member",
                    )
                )
            for assignee in preferred_assignees:
                membership_rows.append(
                    ProjectMember(
                        project_id=project.id,
                        user_id=assignee.id,
                        role_in_project="Member",
                    )
                )

        db.session.add_all(membership_rows)
        db.session.flush()

        batch = []
        sequence = 0
        for task_number in range(1, tasks_per_project + 1):
            for project_number, project in enumerate(generated_projects, start=1):
                sequence += 1
                assignee_index = (sequence - 1) // TASKS_PER_PREFERRED_ASSIGNEE
                assignee_id = (
                    preferred_assignees[assignee_index].id
                    if assignee_index < len(preferred_assignees)
                    else None
                )
                batch.append(
                    Task(
                        project_id=project.id,
                        title=_large_task_title(task_number, project_number, project.name),
                        description=_large_task_description(tag, task_number, project_number),
                        priority=PRIORITIES[(sequence * 3 + task_number // 7) % len(PRIORITIES)],
                        status=STATUSES[(sequence * 5 + task_number // 11) % len(STATUSES)],
                        assignee_id=assignee_id,
                        created_by_id=admin.id,
                        due_date=start + timedelta(days=((sequence * 17) % 180) + 1),
                    )
                )
            if len(batch) >= 500:
                db.session.add_all(batch)
                db.session.flush()
                for task in batch:
                    notify_assignment(task)
                batch.clear()

        if batch:
            db.session.add_all(batch)
            db.session.flush()
            for task in batch:
                notify_assignment(task)

        db.session.commit()
        click.echo("Large test data created.")
        click.echo(f"  Tag:      {tag}")
        click.echo(f"  Users:    {users} (1 admin, {member_count} members)")
        click.echo(f"  Projects: {projects}")
        click.echo(f"  Tasks per project: {tasks_per_project}")
        click.echo(f"  Total tasks:       {projects * tasks_per_project}")
        click.echo(f"  Password for generated users: {LARGE_DATA_PASSWORD}")

    @app.cli.command("clear-large-db")
    @click.option("--tag", default="load", show_default=True)
    @click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
    def clear_large_db(tag, yes):
        """Delete generated large test data by tag without touching real data."""
        tag = _clean_tag(tag)
        project_count = _large_project_query(tag).count()
        user_count = User.query.filter(User.email.like(f"{tag}_%@taskflow.local")).count()
        if not project_count and not user_count:
            click.echo(f"No generated data found for tag '{tag}'.")
            return

        if not yes:
            click.confirm(
                f"Delete generated data with tag '{tag}' "
                f"({user_count} users, {project_count} projects)?",
                abort=True,
            )

        _delete_large_dataset(tag)
        click.echo(f"Generated data with tag '{tag}' cleared.")


def _ensure_task(project, title, description, priority, status, assignee, creator):
    task = Task.query.filter_by(project_id=project.id, title=title).first()
    if task:
        task.description = description
        task.priority = priority
        task.status = status
        task.assignee_id = assignee.id
        task.created_by_id = creator.id
        return

    db.session.add(
        Task(
            project_id=project.id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            assignee_id=assignee.id,
            created_by_id=creator.id,
        )
    )


def _clean_tag(value):
    tag = "".join(ch for ch in value.lower().strip() if ch.isalnum() or ch == "_")
    return tag or "load"


def _members_for_project(members, project_index, members_per_project):
    selected_count = min(members_per_project, len(members))
    return [
        members[(project_index + offset) % len(members)]
        for offset in range(selected_count)
    ]


def _large_marker(tag):
    return f"{LARGE_DATASET_MARKER}: {tag}"


def _large_project_name(index):
    if index <= len(PROJECT_BLUEPRINTS):
        return PROJECT_BLUEPRINTS[index - 1][0]
    return f"Sáng kiến nghiệp vụ chuyên biệt {index:03d}"


def _large_project_description(tag, index):
    if index <= len(PROJECT_BLUEPRINTS):
        scope = PROJECT_BLUEPRINTS[index - 1][1]
    else:
        scope = f"Triển khai phạm vi nghiệp vụ riêng cho sáng kiến số {index:03d}."
    return f"{scope} {_large_marker(tag)}."


def _large_task_title(index, project_number=None, project_name=None):
    value = index - 1
    action = TASK_ACTIONS[value % len(TASK_ACTIONS)]
    subject = TASK_SUBJECTS[(value // len(TASK_ACTIONS)) % len(TASK_SUBJECTS)]
    context_size = len(TASK_ACTIONS) * len(TASK_SUBJECTS)
    context = TASK_CONTEXTS[(value // context_size) % len(TASK_CONTEXTS)]
    project_value = (project_number or 1) - 1
    focus = TASK_FOCUSES[project_value % len(TASK_FOCUSES)]
    phase = TASK_PHASES[(project_value // len(TASK_FOCUSES)) % len(TASK_PHASES)]
    reference = f"{project_number:03d}-{index:04d}" if project_number else f"{index:04d}"
    project_label = f" — {project_name}" if project_name else ""
    return f"{action} {subject} {context}, ưu tiên {focus} trong {phase}{project_label} · CV-{reference}"


def _large_task_description(tag, index, project_number=None):
    project_value = (project_number or 1) - 1
    outcome = TASK_OUTCOMES[(index * 7 + project_value * 3) % len(TASK_OUTCOMES)]
    deliverable = TASK_DELIVERABLES[(index * 3 + index // 10 + project_value) % len(TASK_DELIVERABLES)]
    constraint = TASK_CONSTRAINTS[(index * 9 + project_value * 7) % len(TASK_CONSTRAINTS)]
    focus = TASK_FOCUSES[project_value % len(TASK_FOCUSES)]
    phase = TASK_PHASES[(project_value // len(TASK_FOCUSES)) % len(TASK_PHASES)]
    reference = f"{project_number:03d}-{index:04d}" if project_number else f"{index:04d}"
    return (
        f"Mục tiêu: {outcome}. "
        f"Kết quả bàn giao: {deliverable}. "
        f"Trọng tâm: {focus}, {phase}. "
        f"Điều kiện thực hiện: {constraint}. "
        f"Thực hiện theo phạm vi của công việc CV-{reference}. "
        f"{_large_marker(tag)}."
    )


def _large_project_query(tag):
    return Project.query.filter(
        or_(
            Project.name.like(f"[{tag.upper()}] Project %"),
            Project.description.like(f"%{_large_marker(tag)}%"),
        )
    )


def _delete_large_dataset(tag):
    project_ids = [
        project_id
        for (project_id,) in Project.query
        .with_entities(Project.id)
        .filter(
            or_(
                Project.name.like(f"[{tag.upper()}] Project %"),
                Project.description.like(f"%{_large_marker(tag)}%"),
            )
        )
        .all()
    ]
    user_ids = [
        user_id
        for (user_id,) in User.query
        .with_entities(User.id)
        .filter(User.email.like(f"{tag}_%@taskflow.local"))
        .all()
    ]

    if project_ids:
        task_ids = [
            task_id
            for (task_id,) in Task.query.with_entities(Task.id)
            .filter(Task.project_id.in_(project_ids))
            .all()
        ]
        if task_ids:
            Notification.query.filter(Notification.task_id.in_(task_ids)).delete(synchronize_session=False)
            TaskHistory.query.filter(TaskHistory.task_id.in_(task_ids)).delete(synchronize_session=False)
        Task.query.filter(Task.project_id.in_(project_ids)).delete(synchronize_session=False)
        ProjectMember.query.filter(ProjectMember.project_id.in_(project_ids)).delete(synchronize_session=False)
        Project.query.filter(Project.id.in_(project_ids)).delete(synchronize_session=False)
    if user_ids:
        ProjectMember.query.filter(ProjectMember.user_id.in_(user_ids)).delete(synchronize_session=False)
        Task.query.filter(Task.assignee_id.in_(user_ids)).update({"assignee_id": None}, synchronize_session=False)
        Task.query.filter(Task.created_by_id.in_(user_ids)).update({"created_by_id": None}, synchronize_session=False)
        for user in User.query.filter(User.id.in_(user_ids)).all():
            db.session.delete(user)

    db.session.commit()
