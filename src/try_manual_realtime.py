"""
Realtime autocomplete demo for Module I.

Usage (run from the project root, beside the module1_intake folder):
    python try_manual_realtime.py
    python try_manual_realtime.py "C:\\path\\to\\data"

Typing 2+ characters updates suggestions automatically; Enter is not required.
This UI calls the existing public API: suggest_medication_names().
"""

import sys
import tkinter as tk
from tkinter import messagebox

from module1_intake.api import init_suggester, suggest_medication_names


class ManualAutocompleteApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Module I - Realtime Medication Autocomplete")
        self.root.geometry("850x570")
        self.root.minsize(700, 480)

        self.pending_job = None
        self.results = []

        title = tk.Label(
            root,
            text="Manual Input → Realtime Suggestions",
            font=("Segoe UI", 17, "bold"),
        )
        title.pack(anchor="w", padx=18, pady=(16, 4))

        tk.Label(
            root,
            text="Nhập ít nhất 2 ký tự. Danh sách sẽ tự cập nhật khi bạn gõ, không cần nhấn Enter.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=18, pady=(0, 12))

        tk.Label(root, text="Tên thuốc:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=18
        )
        self.query_var = tk.StringVar()
        self.entry = tk.Entry(
            root, textvariable=self.query_var, font=("Segoe UI", 15), relief="solid", bd=1
        )
        self.entry.pack(fill="x", padx=18, pady=(5, 10), ipady=7)
        self.entry.bind("<KeyRelease>", self.on_key_release)

        body = tk.Frame(root)
        body.pack(fill="both", expand=True, padx=18, pady=5)

        left = tk.Frame(body)
        left.pack(side="left", fill="both", expand=True)

        tk.Label(left, text="Gợi ý từ database (tối đa 5):", font=("Segoe UI", 10, "bold")).pack(
            anchor="w"
        )
        list_frame = tk.Frame(left)
        list_frame.pack(fill="both", expand=True, pady=(5, 0))

        self.listbox = tk.Listbox(
            list_frame, font=("Segoe UI", 11), activestyle="dotbox",
            selectmode=tk.SINGLE, exportselection=False
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        right = tk.Frame(body, bd=1, relief="groove", padx=12, pady=10)
        right.pack(side="right", fill="both", padx=(14, 0))
        tk.Label(right, text="Chi tiết kết quả", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.detail = tk.Text(right, width=39, height=18, wrap="word", font=("Consolas", 10))
        self.detail.pack(fill="both", expand=True, pady=(6, 0))
        self.detail.insert("1.0", "Chọn một gợi ý để xem thông tin thuốc.")
        self.detail.configure(state="disabled")

        self.status_var = tk.StringVar(value="Đang chờ nhập liệu.")
        tk.Label(root, textvariable=self.status_var, anchor="w", relief="sunken").pack(
            fill="x", side="bottom"
        )

        self.entry.focus_set()

    def on_key_release(self, _event=None):
        # Debounce ngắn để tránh gọi tìm kiếm liên tục khi người dùng gõ rất nhanh.
        if self.pending_job is not None:
            self.root.after_cancel(self.pending_job)
        self.pending_job = self.root.after(120, self.update_suggestions)

    def update_suggestions(self):
        self.pending_job = None
        query = self.query_var.get().strip()
        self.listbox.delete(0, tk.END)
        self.results = []
        self.set_detail("Chọn một gợi ý để xem thông tin thuốc.")

        if len(query) < 2:
            self.status_var.set("Nhập thêm ký tự (tối thiểu 2 ký tự).")
            return

        try:
            # Gọi đúng API public hiện có, không viết lại thuật toán autocomplete.
            results = suggest_medication_names(query, limit=5)
        except Exception as exc:
            self.status_var.set(f"Lỗi khi tìm gợi ý: {exc}")
            return

        # CUSTOM_FALLBACK chỉ là nội dung người dùng gõ, không phải thuốc trong data.
        self.results = [
            item for item in results
            if item.get("match_type") != "CUSTOM_FALLBACK"
            and item.get("medication_id")
        ]

        for item in self.results:
            name = item.get("brand_name") or "(Không có tên)"
            strength = item.get("strength") or "Chưa có hàm lượng"
            form = item.get("dosage_form") or "Chưa có dạng bào chế"
            self.listbox.insert(tk.END, f"{name}  |  {strength}  |  {form}")

        if self.results:
            self.status_var.set(
                f"{len(self.results)} gợi ý từ database cho '{query}'. "
                "Chọn một dòng để xem chi tiết."
            )
        else:
            self.status_var.set(f"Không tìm thấy thuốc trong database cho '{query}'.")

    def on_select(self, _event=None):
        selection = self.listbox.curselection()
        if not selection:
            return
        item = self.results[selection[0]]
        lines = [
            f"Tên thuốc: {item.get('brand_name')}",
            f"Medication ID: {item.get('medication_id')}",
            f"Hoạt chất: {item.get('active_ingredient')}",
            f"Hàm lượng: {item.get('strength')}",
            f"Dạng bào chế: {item.get('dosage_form')}",
            f"Match type: {item.get('match_type')}",
            "",
            "Đây là gợi ý từ dictionary; người dùng cần chọn kết quả phù hợp.",
        ]
        self.set_detail("\n".join(lines))

    def set_detail(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", tk.END)
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        # Nạp dictionary và dựng index một lần trước khi mở giao diện.
        init_suggester(data_dir)
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Không thể nạp dữ liệu thuốc",
            f"Chi tiết: {exc}\n\nKiểm tra đường dẫn data và các file CSV."
        )
        root.destroy()
        return

    root = tk.Tk()
    ManualAutocompleteApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
