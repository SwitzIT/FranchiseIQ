// ADD THIS to your existing frontend/src/services/api.js
// (do not replace the file - append this function)

export async function sendChatMessage(messages, sessionId) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, session_id: sessionId || null }),
  });
  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status}`);
  }
  const data = await res.json();
  return data.reply;
}
