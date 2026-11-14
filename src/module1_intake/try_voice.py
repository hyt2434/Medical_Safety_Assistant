import os
from voice import VoiceInputError, WhisperASR, transcribe_voice

# Đảm bảo đúng tên file audio bạn đang dùng để test
audio_path = "sample3.wav"

if not os.path.exists(audio_path):
  print(f"Không tìm thấy file {audio_path}. Hãy đặt file vào cùng thư mục!")
else:
  try:
    print(
        "Đang đọc file và gọi Whisper chạy trên CPU (lần đầu sẽ mất vài giây tải"
        " model)..."
    )

    # Đọc file dưới dạng binary bytes
    with open(audio_path, "rb") as f:
      audio_bytes = f.read()

    # Khởi tạo engine chạy trên CPU và tối ưu int8 để tránh lỗi thiếu CUDA DLL
    cpu_engine = WhisperASR(device="cpu", compute_type="int8")

    # Truyền engine vào hàm transcribe_voice
    result = transcribe_voice(
        audio_bytes, language="en-US", engine=cpu_engine
    )

    print("\n--- KẾT QUẢ THÀNH CÔNG ---")
    print(f"Văn bản nháp (raw_transcript): {result['raw_transcript']}")
    print(f"Điểm tin cậy (confidence_score): {result['confidence_score']}")

  except VoiceInputError as e:
    print(f"\n[LỖI NGHIỆP VỤ] Mã lỗi: {e.code} | Chi tiết: {e.message}")
  except Exception as e:
    print(f"\n[LỖI KHÁC] {type(e).__name__}: {e}")