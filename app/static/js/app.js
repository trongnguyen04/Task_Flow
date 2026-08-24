document.addEventListener("DOMContentLoaded", () => {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

    function hideAlert(alert) {
        alert.style.transition = "opacity 0.4s";
        setTimeout(() => {
            alert.style.opacity = "0";
            setTimeout(() => { alert.style.display = "none"; }, 400);
        }, 3000);
    }

    function showClientAlert(message, category = "info") {
        let alerts = document.querySelector(".page .alerts");
        if (!alerts) {
            const page = document.querySelector(".page") || document.body;
            alerts = document.createElement("div");
            alerts.className = "alerts";
            page.appendChild(alerts);
        }

        const alert = document.createElement("div");
        alert.className = `alert alert-${category}`;
        alert.textContent = message;
        alerts.appendChild(alert);
        hideAlert(alert);
    }

    // ===== Alert auto-hide =====
    document.querySelectorAll(".alert").forEach(alert => {
        hideAlert(alert);
    });

    // ===== Filter dropdowns =====
    document.querySelectorAll(".filter-dropdowns select").forEach(sel => {
        const placeholder = sel.options[0].text;
        Array.from(sel.options).forEach(opt => { opt.dataset.orig = opt.text; });

        function applyPrefix() {
            Array.from(sel.options).forEach(opt => { opt.text = opt.dataset.orig; });
            if (sel.value) {
                const opt = sel.options[sel.selectedIndex];
                opt.text = placeholder + ": " + opt.dataset.orig;
                sel.classList.add("filter-active");
            } else {
                sel.classList.remove("filter-active");
            }
        }

        applyPrefix();
        sel.addEventListener("change", () => {
            Array.from(sel.options).forEach(opt => { opt.text = opt.dataset.orig; });
            sel.closest("form").submit();
        });
    });

    // ===== Priority modal =====
    const priorityModal = document.getElementById("priorityModal");
    if (priorityModal) {
        document.querySelectorAll(".priority-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.getElementById("modalTaskName").textContent = btn.dataset.taskName;
                document.getElementById("priorityForm").action = `/tasks/${btn.dataset.taskId}/priority`;
                const current = btn.dataset.priority.toLowerCase();
                document.querySelectorAll(".priority-option").forEach(opt => {
                    opt.classList.toggle("selected", opt.dataset.priority === current);
                });
                priorityModal.classList.add("open");
            });
        });

        document.getElementById("priorityModalClose").addEventListener("click", () => {
            priorityModal.classList.remove("open");
        });

        priorityModal.addEventListener("click", e => {
            if (e.target === priorityModal) priorityModal.classList.remove("open");
        });
    }

    // ===== Kanban drag-drop =====
    const board = document.querySelector(".kanban-board");
    if (board) {
        let draggedId = null;

        board.querySelectorAll(".kanban-card[draggable='true']").forEach(card => {
            card.addEventListener("dragstart", () => {
                draggedId = card.dataset.taskId;
                card.style.opacity = "0.5";
            });
            card.addEventListener("dragend", () => {
                card.style.opacity = "1";
            });
        });

        board.querySelectorAll(".kanban-cards").forEach(col => {
            col.addEventListener("dragover", e => {
                if (!draggedId) return;
                e.preventDefault();
                col.classList.add("drag-over");
            });
            col.addEventListener("dragleave", () => {
                col.classList.remove("drag-over");
            });
            col.addEventListener("drop", e => {
                e.preventDefault();
                col.classList.remove("drag-over");
                if (!draggedId) return;

                const newStatus = col.dataset.status;
                const card = board.querySelector(`[data-task-id="${draggedId}"]`);
                if (!card) return;
                const sourceCol = card.closest(".kanban-col");
                const destinationCol = col.closest(".kanban-col");
                const sourceStatus = card.closest(".kanban-cards")?.dataset.status;

                card.style.opacity = "0.4";
                card.style.pointerEvents = "none";
                const headers = { "Content-Type": "application/json" };
                if (csrfToken) headers["X-CSRFToken"] = csrfToken;
                fetch(`/api/tasks/${draggedId}`, {
                    method: "PATCH",
                    headers,
                    body: JSON.stringify({ status: newStatus }),
                })
                    .then(r => {
                        if (!r.ok) throw new Error("Không thể cập nhật trạng thái");
                        return r.json();
                    })
                    .then(() => {
                        card.style.opacity = "1";
                        card.style.pointerEvents = "";
                        col.appendChild(card);
                        if (sourceStatus !== newStatus) {
                            updateColumnCount(sourceCol, -1);
                            updateColumnCount(destinationCol, 1);
                        }
                        showClientAlert("Đã cập nhật trạng thái công việc.", "success");
                    })
                    .catch(() => {
                        card.style.opacity = "1";
                        card.style.pointerEvents = "";
                        showClientAlert("Không thể cập nhật trạng thái công việc.", "danger");
                    });

                draggedId = null;
            });
        });

        function updateColumnCount(column, change) {
            if (!column) return;
            const count = Math.max(0, Number(column.dataset.totalCount || 0) + change);
            column.dataset.totalCount = String(count);
            column.querySelector(".kanban-count").textContent = count;
        }
    }

    // ===== Cross-tab logout sync (BroadcastChannel) =====
    const authChannel = (() => {
        try { return new BroadcastChannel("taskflow_auth"); } catch { return null; }
    })();

    if (authChannel) {
        authChannel.onmessage = (e) => {
            if (e.data === "logout") {
                window.location.replace("/login");
            }
        };
    }

    // Khi tab được focus lại, kiểm tra session còn hợp lệ không
    if (document.querySelector(".app-shell")) {
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) {
                fetch("/api/session").then(r => {
                    if (r.status === 401) window.location.replace("/login");
                }).catch(() => {});
            }
        });
    }

    // ===== Shared confirm modal =====
    const confirmModal = document.getElementById("confirmModal");
    if (confirmModal) {
        const confirmForm = document.getElementById("confirmModalForm");
        const confirmMessage = document.getElementById("confirmModalMessage");
        const confirmNext = document.getElementById("confirmModalNext");

        function openConfirmModal(action, message, next) {
            confirmForm.action = action;
            confirmMessage.textContent = message;
            confirmNext.value = next || "";
            confirmModal.classList.add("open");
        }

        function closeConfirmModal() { confirmModal.classList.remove("open"); }

        document.getElementById("confirmModalClose").addEventListener("click", closeConfirmModal);
        document.getElementById("confirmModalCancel").addEventListener("click", closeConfirmModal);
        confirmModal.addEventListener("click", e => { if (e.target === confirmModal) closeConfirmModal(); });

        document.querySelectorAll(".confirm-delete-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                openConfirmModal(btn.dataset.action, btn.dataset.message, btn.dataset.next);
            });
        });
    }

    // ===== Logout confirmation modal =====
    const logoutBtn = document.getElementById("logoutBtn");
    const logoutModal = document.getElementById("logoutModal");
    const logoutModalClose = document.getElementById("logoutModalClose");
    const logoutCancel = document.getElementById("logoutCancel");
    const logoutForm = document.getElementById("logoutForm");

    if (logoutBtn && logoutModal) {
        logoutBtn.addEventListener("click", () => {
            logoutModal.classList.add("open");
        });
        logoutModalClose.addEventListener("click", () => {
            logoutModal.classList.remove("open");
        });
        logoutCancel.addEventListener("click", () => {
            logoutModal.classList.remove("open");
        });
        logoutModal.addEventListener("click", e => {
            if (e.target === logoutModal) logoutModal.classList.remove("open");
        });

        logoutForm.addEventListener("submit", () => {
            // Báo cho tất cả tab khác logout ngay
            if (authChannel) authChannel.postMessage("logout");
        });
    }

});
