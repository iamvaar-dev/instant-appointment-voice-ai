import { useRoomContext } from '@livekit/components-react';
import { useEffect, useState } from 'react';
import { RoomEvent } from 'livekit-client';

export default function ToolVisualizer() {
    const room = useRoomContext();
    const [status, setStatus] = useState("Idle");
    const [history, setHistory] = useState<string[]>([]);

    useEffect(() => {
        if (!room) return;

        const handleData = (payload: Uint8Array) => {
            const str = new TextDecoder().decode(payload);
            try {
                const msg = JSON.parse(str);
                if (msg.type === "tool_call") {
                    setStatus(msg.message);
                    setHistory(prev => [...prev, `Called: ${msg.message}`]);
                } else if (msg.type === "tool_result") {
                    setStatus(`Result: ${msg.message}`);
                    setHistory(prev => [...prev, `Result: ${msg.message}`]);
                }
            } catch (e) {
                // ignore non-json
            }
        };

        room.on(RoomEvent.DataReceived, handleData);
        return () => {
            room.off(RoomEvent.DataReceived, handleData);
        };
    }, [room]);

    return (
        <div className="tool-visualizer" style={{ marginTop: '2rem', padding: '1rem', border: '1px solid #333', borderRadius: '8px', maxWidth: '600px', width: '100%' }}>
            <h3>Agent Activity</h3>
            <div className="current-status" style={{ fontWeight: 'bold', marginBottom: '1rem', color: '#00ccff' }}>
                {status}
            </div>
            <div className="history" style={{ maxHeight: '150px', overflowY: 'auto', fontSize: '0.9rem', color: '#ccc' }}>
                {history.map((h, i) => <div key={i}>{h}</div>)}
            </div>
        </div>
    );
}
