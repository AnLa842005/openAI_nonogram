# Nonograms Studio

Bài tập lớn 1 – Tìm kiếm (Nhập môn Trí tuệ Nhân tạo, CO3061). Chương trình giải
**Nonograms** bằng hai thuật toán, viết bằng Python 3, có giao diện
trực quan hóa từng bước bằng PySide6:

- **DFS** (blind search): gán lần lượt từng hàng, từ trên xuống.
- **Heuristic**: lan truyền ràng buộc kết hợp MRV, đoán từng ô khi cần.

## 1. Cài đặt

Yêu cầu Python ≥ 3.10. Chạy trong thư mục gốc của project:

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

> macOS/Linux: thay `py -3` bằng `python3` và `.venv\Scripts\python` bằng `.venv/bin/python`.

## 2. Chạy test

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

43 test. Một số test quan trọng:

```powershell
# Cả hai thuật toán phải ra đúng đáp án chính thức của puzzle-nonograms.com
.venv\Scripts\python -m unittest tests.test_examples -v

# Từng thuật toán: puzzle ngẫu nhiên, trường hợp vô nghiệm, hủy giữa chừng, quay lui
.venv\Scripts\python -m unittest tests.test_dfs_solver -v
.venv\Scripts\python -m unittest tests.test_heuristic_solver -v
```

## 3. Mở visualizer

```powershell
.venv\Scripts\python -m nonogram_visualizer
```

1. **New Puzzle → Examples** để chọn một puzzle thật (5×5 → 30×30), hoặc
   **New Puzzle → Random Puzzle…** để sinh puzzle theo kích thước và seed.
2. Bấm nút chế độ **Visualize** ở bảng bên phải.
3. Chọn thuật toán **DFS** hoặc **Heuristic (MRV + propagation)**.
4. Bấm **Run** để chạy tự động (chỉnh tốc độ bằng thanh trượt), **Pause** để
   dừng, **Next Step** để xem từng bước, **Reset** để chạy lại từ đầu.

Bảng bên phải hiển thị bước hiện tại (TRY / ACCEPT / REJECT / BACKTRACK…), số
nút, số lần quay lui, độ sâu và thời gian chạy của thuật toán.

Chế độ **Play** cho phép tự giải bằng chuột: chuột trái tô ô, chuột phải đánh dấu
trống, bấm **Check** để kiểm tra.

## 4. Đo thời gian và bộ nhớ (số liệu cho báo cáo)

Chạy không giao diện, `--memory` đo thêm bộ nhớ đỉnh bằng `tracemalloc`:

```powershell
.venv\Scripts\python -m nonogram_visualizer.dfs_solver       examples/puzzle-nonograms/15x15.json --memory
.venv\Scripts\python -m nonogram_visualizer.heuristic_solver examples/puzzle-nonograms/15x15.json --memory
```

Kết quả in ra gồm trạng thái, số nút, số lần quay lui, độ sâu,
`solver_time_ms`, bộ nhớ đỉnh và lời giải. Thay tên file để chạy các kích thước
khác. Lưu ý: DFS trên `25x25.json` và `30x30_special_weekly.json` chạy hơn 2 phút
chưa xong; Heuristic giải mọi file trong dưới 1 giây.

## 5. Cấu trúc project

```text
nonogram_visualizer/
  dfs_solver.py         # Thuật toán DFS + sinh mẫu dòng + đo hiệu năng/CLI dùng chung
  heuristic_solver.py   # Thuật toán Heuristic: lan truyền ràng buộc + MRV
  models.py             # Puzzle, SearchStep, SearchStats; kiểm tra input JSON
  solvers.py            # Giao diện Solver chung + chạy thuật toán trên thread riêng
  generator.py          # Sinh puzzle ngẫu nhiên theo seed
  board_logic.py        # Logic chế độ Play
  ui/                   # Giao diện PySide6 (cửa sổ, bàn cờ, bảng điều khiển)
examples/
  puzzle-nonograms/     # 7 puzzle thật kèm mã băm đáp án chính thức
  cross_5x5.json
tests/                  # unittest cho thuật toán, input, generator và giao diện
```

Định dạng puzzle (JSON):

```json
{
  "name": "Cross 5x5",
  "row_clues": [[1], [3], [5], [3], [1]],
  "col_clues": [[1], [3], [5], [3], [1]]
}
```

Dòng không có ô tô ghi là `[]`. Puzzle trong `examples/puzzle-nonograms/` có thêm
`metadata.task` và `metadata.hashed_solution` của trang web; test tính lại
`md5(task + lời giải)` để so với đáp án chính thức.

## 6. Quy ước thống kê

| Trường | DFS | Heuristic |
| --- | --- | --- |
| `nodes_generated` | số lần thử gán một mẫu cho một hàng | số lần thử một giá trị cho ô đoán |
| `nodes_expanded` | số trạng thái được mở rộng (tính cả gốc) | số lần lan truyền bế tắc, phải đoán |
| `backtracks` | số lựa chọn bị bỏ vì nhánh con thất bại | như DFS |
| `max_depth` | số hàng đã gán | số lần đoán lồng nhau |
| `solver_time_ms` | thời gian tính toán, không gồm thời gian vẽ giao diện | như DFS |
| `peak_memory_bytes` | bộ nhớ đỉnh (tracemalloc), đo ở lần chạy riêng | như DFS |

Giá trị không có được hiển thị là `—`.
