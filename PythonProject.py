# -*- coding: utf-8 -*-
"""
Student Database System with GUI + Smooth Sorting Visualizations (fixed)
- Smooth block movement animations
- Fixed: properly reset internal lists when reloading data
- Highlighted active, comparing, and sorted elements
- Dark-mode GUI using CustomTkinter
- SQLite-backed student records (Add, Delete, Update)
"""

import sqlite3
import time
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

# ---------- Database Manager ----------
DB_FILENAME = "students.db"

class DBManager:
    def __init__(self, filename=DB_FILENAME):
        self.conn = sqlite3.connect(filename)
        self.create_table()

    def create_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll TEXT NOT NULL UNIQUE,
            marks INTEGER NOT NULL
        )
        """
        self.conn.execute(sql)
        self.conn.commit()

    def add_student(self, name, roll, marks):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO students (name, roll, marks) VALUES (?, ?, ?)", (name, roll, marks))
        self.conn.commit()
        return cur.lastrowid

    def update_student(self, sid, name, roll, marks):
        self.conn.execute("UPDATE students SET name=?, roll=?, marks=? WHERE id=?", (name, roll, marks, sid))
        self.conn.commit()

    def delete_student(self, sid):
        self.conn.execute("DELETE FROM students WHERE id=?", (sid,))
        self.conn.commit()

    def fetch_all(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name, roll, marks FROM students ORDER BY id")
        return cur.fetchall()

    def close(self):
        self.conn.close()


# ---------- Visualizer (Smooth Animation) ----------
class SortVisualizer:
    def __init__(self, canvas: tk.Canvas, speed_scale: tk.Scale):
        self.canvas = canvas
        self.speed_scale = speed_scale
        self.data = []
        self.bar_items = []
        self.text_items = []
        self.width = int(canvas["width"])
        self.height = int(canvas["height"])
        self.padding = 40
        self.running = False

    def load_data(self, data_list):
        """Load and draw bars. Clears previous canvas items AND internal lists."""
        # clear canvas and internal references
        self.canvas.delete("all")
        self.bar_items = []
        self.text_items = []
        self.data = [list(d) for d in data_list]

        n = len(self.data)
        if n == 0:
            return

        max_val = max(d[3] for d in self.data) if any(d[3] is not None for d in self.data) else 1
        # compute bar width safely
        total_gap = (n - 1) * 10
        available_width = max(100, self.width - 2 * self.padding)
        bar_width = max(10, (available_width - total_gap) / n)

        for i, d in enumerate(self.data):
            x0 = self.padding + i * (bar_width + 10)
            y1 = self.height - 40
            # scale height; avoid division by zero
            bar_height = (d[3] / max_val) * (self.height - 100) if max_val > 0 else 10
            y0 = y1 - bar_height
            rect = self.canvas.create_rectangle(x0, y0, x0 + bar_width, y1, fill="#2b7a78", outline="")
            text = self.canvas.create_text(x0 + bar_width / 2, y0 - 15, text=str(d[3]), fill="white", font=("Arial", 10))
            name_text = self.canvas.create_text(x0 + bar_width / 2, y1 + 10, text=d[1], fill="white", font=("Arial", 8))
            self.bar_items.append(rect)
            self.text_items.append((text, name_text))
        self.canvas.update()

    def get_speed(self):
        val = self.speed_scale.get()
        # map slider to sleep delay; clamp small value
        return max(0.001, (101 - val) / 700)

    def move_bar(self, index, dx, dy, steps=20):
        """Smooth move of bar index by dx, dy in small increments."""
        if index < 0 or index >= len(self.bar_items):
            return
        for _ in range(steps):
            # move rectangle
            self.canvas.move(self.bar_items[index], dx / steps, dy / steps)
            # move texts
            t, n = self.text_items[index]
            self.canvas.move(t, dx / steps, dy / steps)
            self.canvas.move(n, dx / steps, dy / steps)
            self.canvas.update()
            time.sleep(self.get_speed())

    def swap_bars(self, i, j):
        """Smoothly swap two bars visually and swap internal bookkeeping."""
        if i == j:
            return
        if not (0 <= i < len(self.bar_items) and 0 <= j < len(self.bar_items)):
            return

        # compute current x positions (left coordinate of rectangle)
        coords_i = self.canvas.coords(self.bar_items[i])
        coords_j = self.canvas.coords(self.bar_items[j])
        if not coords_i or not coords_j:
            return
        x1 = coords_i[0]
        x2 = coords_j[0]
        dx = x2 - x1

        # lift both bars
        self.move_bar(i, 0, -30)
        # note: after moving i, bar indices still valid because we move items in place
        # move j (index j may have changed visually but indices remain same)
        self.move_bar(j, 0, -30)

        # slide horizontally (i -> j pos, j -> i pos)
        self.move_bar(i, dx, 0)
        self.move_bar(j, -dx, 0)

        # drop both bars
        self.move_bar(i, 0, 30)
        self.move_bar(j, 0, 30)

        # swap lists so indices reflect new order
        self.bar_items[i], self.bar_items[j] = self.bar_items[j], self.bar_items[i]
        self.text_items[i], self.text_items[j] = self.text_items[j], self.text_items[i]
        self.data[i], self.data[j] = self.data[j], self.data[i]
        self.canvas.update()

    def highlight(self, indices, color):
        for i in indices:
            if 0 <= i < len(self.bar_items):
                self.canvas.itemconfig(self.bar_items[i], fill=color)
        self.canvas.update()

    def reset_colors(self):
        for i in range(len(self.bar_items)):
            try:
                self.canvas.itemconfig(self.bar_items[i], fill="#2b7a78")
            except tk.TclError:
                pass
        self.canvas.update()

    def insertion_sort(self, callback=None):
        self.running = True
        n = len(self.data)
        for i in range(1, n):
            if not self.running:
                break
            j = i
            self.highlight([i], "#fdd835")  # mark current key
            time.sleep(self.get_speed())
            while j > 0 and self.data[j - 1][3] > self.data[j][3]:
                if not self.running:
                    break
                self.highlight([j, j - 1], "#cc241d")
                # visually swap the bars j and j-1
                self.swap_bars(j, j - 1)
                # mark swapped item as part of sorted prefix for this pass
                self.highlight([j - 1], "#66bb6a")
                j -= 1
                if callback:
                    callback(self.data)
                time.sleep(self.get_speed())
            self.reset_colors()
        # final: mark all sorted
        self.highlight(list(range(n)), "#388e3c")
        self.running = False

    def selection_sort(self, callback=None):
        self.running = True
        n = len(self.data)
        for i in range(n):
            if not self.running:
                break
            min_idx = i
            self.highlight([i], "#fdd835")
            for j in range(i + 1, n):
                if not self.running:
                    break
                self.highlight([j], "#cc241d")
                time.sleep(self.get_speed())
                if self.data[j][3] < self.data[min_idx][3]:
                    min_idx = j
                # reset small highlights except the found min and i
                self.reset_colors()
                self.highlight([i, min_idx], "#fdd835")
            if not self.running:
                break
            if min_idx != i:
                self.swap_bars(i, min_idx)
                if callback:
                    callback(self.data)
            # mark prefix as sorted up to i
            self.highlight(list(range(i + 1)), "#66bb6a")
        self.highlight(list(range(n)), "#388e3c")
        self.running = False

    def stop(self):
        self.running = False


# ---------- GUI ----------
class StudentApp:
    def __init__(self, root):
        self.root = root
        self.db = DBManager()
        self.root.title("Student Database System — Smooth Sort Visualizer (fixed)")
        self.root.geometry("1000x650")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Layout
        self.left_frame = ctk.CTkFrame(root, width=320, corner_radius=8)
        self.left_frame.pack(side="left", fill="y", padx=12, pady=12)

        self.right_frame = ctk.CTkFrame(root, corner_radius=8)
        self.right_frame.pack(side="right", expand=True, fill="both", padx=12, pady=12)

        self._build_controls()
        self._build_table()
        self._build_visuals()
        self.load_table()

        self.selected_id = None
        self.sort_thread = None

    def _build_controls(self):
        parent = self.left_frame
        title = ctk.CTkLabel(parent, text="Controls", font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(pady=(6, 12))

        self.name_entry = ctk.CTkEntry(parent, placeholder_text="Name")
        self.name_entry.pack(fill="x", pady=5)
        self.roll_entry = ctk.CTkEntry(parent, placeholder_text="Roll No")
        self.roll_entry.pack(fill="x", pady=5)
        self.marks_entry = ctk.CTkEntry(parent, placeholder_text="Marks (integer)")
        self.marks_entry.pack(fill="x", pady=5)

        ctk.CTkButton(parent, text="Add", command=self.add_student).pack(fill="x", pady=4)
        ctk.CTkButton(parent, text="Update", command=self.update_student).pack(fill="x", pady=4)
        ctk.CTkButton(parent, text="Delete", command=self.delete_student).pack(fill="x", pady=4)

        sep = ctk.CTkLabel(parent, text="\nSorting Visualizer", font=ctk.CTkFont(size=14, weight="bold"))
        sep.pack(pady=(10, 4))

        self.speed_scale = ctk.CTkSlider(parent, from_=1, to=100)
        self.speed_scale.set(40)
        self.speed_scale.pack(fill="x", pady=4)

        ctk.CTkButton(parent, text="Insertion Sort", command=self.start_insertion_sort).pack(fill="x", pady=4)
        ctk.CTkButton(parent, text="Selection Sort", command=self.start_selection_sort).pack(fill="x", pady=4)
        ctk.CTkButton(parent, text="Stop Sorting", fg_color="#b22222", command=self.stop_sorting).pack(fill="x", pady=4)

    def _build_table(self):
        frame = ctk.CTkFrame(self.right_frame)
        frame.pack(fill="x", padx=6, pady=(6, 0))
        cols = ("id", "name", "roll", "marks")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=8)
        for col in cols:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, anchor=tk.CENTER)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        sb.pack(side="right", fill="y")

    def _build_visuals(self):
        vis_frame = ctk.CTkFrame(self.right_frame)
        vis_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.canvas = tk.Canvas(vis_frame, width=620, height=360, bg="#1f1f1f", highlightthickness=0)
        self.canvas.pack(pady=8)
        self.visualizer = SortVisualizer(self.canvas, self.speed_scale)
        self.info_label = ctk.CTkLabel(vis_frame, text="Ready", anchor="w")
        self.info_label.pack(fill="x")

    def load_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = self.db.fetch_all()
        for r in rows:
            self.tree.insert("", tk.END, values=r)
        # load visuals using latest DB state
        self.visualizer.load_data(rows)

    def on_row_select(self, _=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])["values"]
        if vals:
            sid, name, roll, marks = vals
            self.selected_id = sid
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, name)
            self.roll_entry.delete(0, tk.END)
            self.roll_entry.insert(0, roll)
            self.marks_entry.delete(0, tk.END)
            self.marks_entry.insert(0, str(marks))

    def add_student(self):
        name, roll, marks = self.name_entry.get().strip(), self.roll_entry.get().strip(), self.marks_entry.get().strip()
        if not name or not roll or not marks:
            messagebox.showwarning("Missing", "Fill all fields")
            return
        try:
            marks = int(marks)
        except ValueError:
            messagebox.showerror("Invalid", "Marks must be integer")
            return
        try:
            self.db.add_student(name, roll, marks)
            self.load_table()
            self.clear_form()
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "Roll number must be unique")

    def update_student(self):
        if not self.selected_id:
            messagebox.showwarning("Select", "Select a student to update.")
            return
        name, roll, marks = self.name_entry.get().strip(), self.roll_entry.get().strip(), self.marks_entry.get().strip()
        if not name or not roll or not marks:
            messagebox.showwarning("Missing", "Fill all fields")
            return
        try:
            marks = int(marks)
        except ValueError:
            messagebox.showerror("Invalid", "Marks must be integer")
            return
        try:
            self.db.update_student(self.selected_id, name, roll, marks)
            self.load_table()
            self.clear_form()
            self.selected_id = None
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "Roll number must be unique")

    def delete_student(self):
        if not self.selected_id:
            messagebox.showwarning("Select", "Select a student to delete.")
            return
        if not messagebox.askyesno("Confirm", "Delete selected student?"):
            return
        self.db.delete_student(self.selected_id)
        self.load_table()
        self.clear_form()
        self.selected_id = None

    def clear_form(self):
        self.name_entry.delete(0, tk.END)
        self.roll_entry.delete(0, tk.END)
        self.marks_entry.delete(0, tk.END)

    def start_insertion_sort(self):
        if self.sort_thread and self.sort_thread.is_alive():
            return messagebox.showinfo("Sorting", "Already running.")
        rows = self.db.fetch_all()
        if not rows:
            return messagebox.showinfo("Empty", "No data.")
        self.visualizer.load_data(rows)
        self.info_label.configure(text="Insertion Sort running...")
        self.sort_thread = threading.Thread(target=self._run_sort, args=("insertion",), daemon=True)
        self.sort_thread.start()

    def start_selection_sort(self):
        if self.sort_thread and self.sort_thread.is_alive():
            return messagebox.showinfo("Sorting", "Already running.")
        rows = self.db.fetch_all()
        if not rows:
            return messagebox.showinfo("Empty", "No data.")
        self.visualizer.load_data(rows)
        self.info_label.configure(text="Selection Sort running...")
        self.sort_thread = threading.Thread(target=self._run_sort, args=("selection",), daemon=True)
        self.sort_thread.start()

    def _run_sort(self, algo):
        def update_table(data):
            # update the treeview on main thread
            self.root.after(0, lambda: self._refresh_table(data))
        if algo == "insertion":
            self.visualizer.insertion_sort(update_table)
        else:
            self.visualizer.selection_sort(update_table)
        self.root.after(0, lambda: self.info_label.configure(text=f"{algo.capitalize()} Sort Finished"))
        # final refresh from visualizer state
        self.root.after(0, lambda: self._refresh_table(self.visualizer.data))

    def _refresh_table(self, data):
        # data is list of [id, name, roll, marks]
        for i in self.tree.get_children():
            self.tree.delete(i)
        for d in data:
            self.tree.insert("", tk.END, values=d)

    def stop_sorting(self):
        if self.visualizer.running:
            self.visualizer.stop()
            self.info_label.configure(text="Stopping...")

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.visualizer.stop()
            self.db.close()
            self.root.destroy()


if __name__ == "__main__":
    root = ctk.CTk()
    app = StudentApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
