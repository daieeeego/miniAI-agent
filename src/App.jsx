import React, { useState } from "react";
import { reply } from "./agent.js";

export default function App() {
  const [input, setInput] = useState("");
  const [log, setLog] = useState([]);

  const send = (e) => {
    e.preventDefault();
    setLog((prev) => [...prev, { user: input, agent: reply(input) }]);
    setInput("");
  };

  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: 16 }}>
      <h1>ミニAIエージェント</h1>
      <ul>
        {log.map((m, i) => (
          <li key={i}>
            <div>あなた: {m.user}</div>
            <div>エージェント: {m.agent}</div>
          </li>
        ))}
      </ul>
      <form onSubmit={send}>
        <input value={input} onChange={(e) => setInput(e.target.value)} />
        <button type="submit">送信</button>
      </form>
    </main>
  );
}
