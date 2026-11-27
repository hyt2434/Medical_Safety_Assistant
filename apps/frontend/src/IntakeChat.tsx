import { useEffect, useRef, useState } from "react";
import { ArrowRight, History, Search, Send, ShieldCheck, Volume2 } from "lucide-react";
import { Badge, Card, CardHeading, Notice } from "./components";
import { TieuBachAvatar } from "./TieuBach";
import type { IntakeDetails } from "./api";

/** Original chat layout, with exchanges owned by Core rather than local demo replies. */
export function IntakeChat({ messages, value, onChange, onSend, disabled }: {
  messages: IntakeDetails["messages"]; value: string; onChange: (value: string) => void;
  onSend: (text: string) => void; disabled: boolean;
}) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("");
  const [speechError, setSpeechError] = useState("");
  const scroll = useRef<HTMLDivElement>(null);
  const exchanges = messages.filter(item => ["USER", "ASSISTANT"].includes(item.role));
  const questions = exchanges.filter(item => item.role === "USER");
  useEffect(() => { scroll.current?.scrollTo({ top: scroll.current.scrollHeight }); }, [messages]);
  useEffect(() => () => { if ("speechSynthesis" in window) speechSynthesis.cancel(); }, []);
  function read(text: string) {
    if (!("speechSynthesis" in window)) { setSpeechError("Trình duyệt chưa hỗ trợ đọc văn bản."); return; }
    speechSynthesis.cancel();
    const speech = new SpeechSynthesisUtterance(text); speech.lang = "vi-VN";
    speech.onerror = () => setSpeechError("Không thể đọc nội dung. Bạn có thể đọc trực tiếp trên màn hình.");
    speechSynthesis.speak(speech);
  }
  return <div className="chat-layout">
    <aside className="chat-sidebar">
      <Card><span className="chat-avatar"><TieuBachAvatar /></span><h2>Tiểu Bạch</h2>
        <Badge tone="neutral">Trợ lý thuốc</Badge><p>Những hỏi thường gặp</p>
        <div className="chat-topics">{["Giải thích kết quả của tôi", "Tôi nên hỏi dược sĩ gì?", "Nguồn dữ liệu ở đâu?", "Cách nhập toa thuốc"].map(prompt =>
          <button key={prompt} disabled={disabled} onClick={() => onSend(prompt)}>{prompt}<ArrowRight size={16} /></button>)}</div>
      </Card>
      <Card className="chat-history-card">
        <CardHeading icon={<History size={21} />} title="Lịch sử câu hỏi" detail={`${questions.length} câu hỏi trong phiên này`} />
        {questions.length > 0 && <div className="search-input"><Search size={17} /><input aria-label="Tìm trong lịch sử câu hỏi" placeholder="Tìm câu đã hỏi..." value={search} onChange={event => setSearch(event.target.value)} /></div>}
        <nav className="question-history" aria-label="Lịch sử câu hỏi">{questions.filter(item => (item.text_content || "").toLocaleLowerCase("vi").includes(search.toLocaleLowerCase("vi"))).reverse().map(item =>
          <button key={item.id} className={selected === item.id ? "selected" : ""} onClick={() => {
            setSelected(item.id); document.getElementById(`chat-${item.id}`)?.scrollIntoView({ block: "nearest" });
          }}><span>{item.text_content}</span></button>)}</nav>
        {!questions.length && <p className="history-empty">Các câu bạn hỏi sẽ xuất hiện ở đây để dễ tìm lại.</p>}
      </Card>
      <Notice>Trợ lý không chẩn đoán, kê đơn hoặc thay đổi thuốc.</Notice>
    </aside>
    <section className="chat-panel">
      <div className="chat-panel-header"><span className="icon-tile"><TieuBachAvatar compact /></span><div><strong>Tiểu Bạch · Trợ lý thuốc</strong></div><ShieldCheck size={22} /></div>
      <div className="chat-messages" ref={scroll} role="log" aria-label="Hội thoại đã lưu" aria-live="polite">
        {!exchanges.length && <div className="chat-message assistant"><small>Tiểu Bạch</small><p>Bạn có thể nhập thông tin thuốc hoặc câu hỏi tại đây.</p></div>}
        {exchanges.map(item => <div key={item.id} id={`chat-${item.id}`} tabIndex={-1} className={`chat-message ${item.role === "USER" ? "user" : "assistant"}${selected === item.id ? " selected" : ""}`}>
          <small>{item.role === "USER" ? "Bạn" : "Tiểu Bạch"}</small><p style={{ whiteSpace: "pre-wrap" }}>{item.text_content}</p>
          {item.role === "ASSISTANT" && <button className="text-button" onClick={() => read(item.text_content || "")}><Volume2 size={15} /> Nghe nội dung</button>}
        </div>)}
      </div>
      <form className="chat-compose" onSubmit={event => { event.preventDefault(); onSend(value); }}>
        <label className="sr-only" htmlFor="chat-input">Tin nhắn</label>
        <textarea id="chat-input" value={value} maxLength={12000} disabled={disabled} onChange={event => onChange(event.target.value)} placeholder="Bạn muốn hỏi điều gì?" rows={2} />
        <button className="button" disabled={disabled || !value.trim()} aria-label="Gửi tin nhắn" type="submit"><Send size={20} /><span>Gửi</span></button>
      </form>
      <p className="chat-footnote" role="status">{speechError || "Câu trả lời không thay thế tư vấn y khoa."}</p>
    </section>
  </div>;
}
