import { useEffect, useState, useRef } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useTracks,
  VideoTrack,
  useRoomContext,
  useConnectionState,
  useDisconnectButton,
  TrackToggle,
} from '@livekit/components-react';
import { Track, ConnectionState } from 'livekit-client';
import '@livekit/components-styles';
import './App.css';
import ToolVisualizer from './components/ToolVisualizer';

function App() {
  const [token, setToken] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [hasEverConnected, setHasEverConnected] = useState(false);
  const userInitiatedDisconnect = useRef(false);
  const didFetch = useRef(false);

  const url = import.meta.env.VITE_LIVEKIT_URL;

  useEffect(() => {
    if (didFetch.current) return;
    didFetch.current = true;

    // Fetch user token from our backend
    const backendUrl = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
    fetch(`${backendUrl}/getToken?name=User`)
      .then(res => res.json())
      .then(data => setToken(data.token));
  }, []);

  if (!token) return <div className="loading">Initializing Neural Interface...</div>;

  if (!isConnected) {
    return (
      <div className="pre-join-screen">
        <h1>Clinic Voice Assistant</h1>
        <button className="start-button" onClick={() => setIsConnected(true)}>
          Start Consultation
        </button>
      </div>
    );
  }

  const handleConnected = () => {
    console.log("Connected to room");
    setHasEverConnected(true);
  };

  const handleDisconnected = () => {
    console.log("Disconnected from room");
    // If user initiated the disconnect, go straight back to start
    if (userInitiatedDisconnect.current) {
      userInitiatedDisconnect.current = false;
      setIsConnected(false);
      setHasEverConnected(false);
      return;
    }
    // Otherwise, if we never connected, also go back to start
    if (!hasEverConnected) {
      setIsConnected(false);
    }
    // If hasEverConnected is true, we'll let RoomContent handle showing reconnect overlay
  };

  return (
    <LiveKitRoom
      video={false} // Don't publish my video
      audio={true}  // Publish my audio
      token={token}
      serverUrl={url}
      connect={true}
      data-lk-theme="default"
      className="lk-room-container"
      onConnected={handleConnected}
      onDisconnected={handleDisconnected}
    >
      <RoomContent setIsConnected={setIsConnected} userInitiatedDisconnect={userInitiatedDisconnect} />
    </LiveKitRoom>
  );
}

function RoomContent({ setIsConnected, userInitiatedDisconnect }: {
  setIsConnected: (v: boolean) => void;
  userInitiatedDisconnect: React.MutableRefObject<boolean>;
}) {
  const [permissionsGranted, setPermissionsGranted] = useState(false);
  const [systemStatus, setSystemStatus] = useState({
    stt: 'pending',
    llm: 'pending',
    tts: 'pending',
    database: 'pending',
    avatar: 'pending'
  });
  const [wasEverReady, setWasEverReady] = useState(false);

  const tracks = useTracks([Track.Source.Camera, Track.Source.Microphone]);
  const videoTrack = tracks.find(t => t.publication.kind === Track.Kind.Video);
  const room = useRoomContext();
  const connectionState = useConnectionState();

  // Listen for system status updates from backend
  useEffect(() => {
    if (!room) {
      console.log("Room not ready yet");
      return;
    }

    console.log("Setting up data listener for room:", room.name);

    const handleDataReceived = (payload: Uint8Array, _participant: any) => {
      const decoder = new TextDecoder();
      const message = decoder.decode(payload);

      console.log("Received data:", message);

      try {
        const data = JSON.parse(message);
        if (data.type === 'system_status') {
          console.log(`System status: ${data.component} -> ${data.status}`);
          setSystemStatus(prev => ({
            ...prev,
            [data.component]: data.status
          }));
        }
      } catch (e) {
        console.log("Non-JSON message:", message);
      }
    };

    room.on('dataReceived', handleDataReceived);
    console.log("Data listener attached");

    return () => {
      console.log("Removing data listener");
      room.off('dataReceived', handleDataReceived);
    };
  }, [room]);

  // Request permissions ONLY after connected to room
  useEffect(() => {
    if (connectionState !== ConnectionState.Connected) {
      console.log("Waiting for room connection before requesting permissions...");
      return;
    }

    if (permissionsGranted) return;

    const requestPermissions = async () => {
      try {
        console.log("Room connected. Requesting microphone permissions...");
        await navigator.mediaDevices.getUserMedia({ audio: true });

        try {
          await navigator.mediaDevices.getUserMedia({ video: true });
        } catch (err) {
          console.log("Camera access denied (optional)");
        }

        console.log("Permissions granted");
        setPermissionsGranted(true);
      } catch (err) {
        console.error("Microphone access denied:", err);
        alert("Microphone access is required. Please allow microphone access and refresh.");
      }
    };

    requestPermissions();
  }, [connectionState, permissionsGranted]);

  // Check if all systems are ready AND avatar video is streaming
  const avatarReady = systemStatus.avatar === 'ready' && videoTrack !== undefined;
  const avatarUnavailable = systemStatus.avatar === 'unavailable' || systemStatus.avatar === 'error';

  const allSystemsReady =
    connectionState === ConnectionState.Connected &&
    permissionsGranted &&
    systemStatus.stt === 'ready' &&
    systemStatus.llm === 'ready' &&
    systemStatus.tts === 'ready' &&
    systemStatus.database === 'ready' &&
    (avatarReady || avatarUnavailable);

  console.log("System status:", systemStatus);
  console.log("All systems ready:", allSystemsReady);
  console.log("Avatar ready:", avatarReady, "Video track:", !!videoTrack);

  // Track if we were ever ready (to distinguish reconnecting from initial loading)
  useEffect(() => {
    if (allSystemsReady && !wasEverReady) {
      setWasEverReady(true);
    }
  }, [allSystemsReady, wasEverReady]);

  // Detect reconnecting state from connection state
  const isReconnecting = wasEverReady && connectionState === ConnectionState.Reconnecting;
  const isDisconnected = wasEverReady && connectionState === ConnectionState.Disconnected;

  // Handle disconnection timeout - if disconnected for too long, go back to start
  useEffect(() => {
    if (!isDisconnected) return;

    const timeout = setTimeout(() => {
      console.log("Disconnect timeout - returning to start");
      setIsConnected(false);
    }, 30000); // 30 second timeout

    return () => clearTimeout(timeout);
  }, [isDisconnected, setIsConnected]);

  // Show loading screen until all systems are ready (unless reconnecting)
  if (!allSystemsReady && !wasEverReady) {
    return (
      <div className="loading-screen-container">
        <div className="loading-content">
          <div className="avatar-icon" style={{
            animation: 'pulse 1.5s infinite',
            fontSize: '5rem',
            marginBottom: '2rem'
          }}>🤖</div>

          <h2 style={{ marginBottom: '2rem' }}>Warming Up Systems</h2>

          <div className="system-status-list">
            <SystemStatusItem
              icon="🔐"
              label="Permissions"
              status={permissionsGranted ? 'ready' : 'pending'}
            />
            <SystemStatusItem
              icon="🎤"
              label="Speech-to-Text"
              status={systemStatus.stt}
            />
            <SystemStatusItem
              icon="🧠"
              label="AI Model"
              status={systemStatus.llm}
            />
            <SystemStatusItem
              icon="🔊"
              label="Text-to-Speech"
              status={systemStatus.tts}
            />
            <SystemStatusItem
              icon="💾"
              label="Database"
              status={systemStatus.database}
            />
            <SystemStatusItem
              icon="👤"
              label="Avatar"
              status={videoTrack ? 'ready' : (systemStatus.avatar === 'ready' ? 'initializing' : systemStatus.avatar)}
            />
          </div>
        </div>
      </div>
    );
  }

  // Only show call screen after all systems are ready
  return (
    <>
      {(isReconnecting || isDisconnected) && (
        <div className="reconnecting-overlay">
          <div className="reconnecting-content">
            <div className="reconnecting-spinner">⟳</div>
            <h3>{isDisconnected ? 'Connection Lost' : 'Reconnecting...'}</h3>
            <p>{isDisconnected ? 'Attempting to reconnect...' : 'Please wait...'}</p>
          </div>
        </div>
      )}

      <h1>Clinic Voice Assistant</h1>

      <div className="avatar-container">
        <AvatarRenderer />
      </div>

      <div className="controls">
        <RoomAudioRenderer />
        <CustomControlBar userInitiatedDisconnect={userInitiatedDisconnect} />
      </div>

      <ToolVisualizer />
      <TrackDebug />
    </>
  );
}

function SystemStatusItem({ icon, label, status }: { icon: string; label: string; status: string }) {
  const getStatusColor = () => {
    switch (status) {
      case 'ready': return '#00ff88';
      case 'initializing': return '#ffaa00';
      case 'error': return '#ff4444';
      case 'unavailable': return '#888888';
      default: return '#555555';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'ready': return '✓ Ready';
      case 'initializing': return '⟳ Loading...';
      case 'error': return '✗ Error';
      case 'unavailable': return '- Unavailable';
      default: return '○ Waiting...';
    }
  };

  return (
    <div className="status-item" style={{ color: getStatusColor() }}>
      <span className="status-icon">{icon}</span>
      <span className="status-label">{label}</span>
      <span className="status-text">{getStatusText()}</span>
    </div>
  );
}

function TrackDebug() {
  const tracks = useTracks();
  return (
    <div style={{ position: 'absolute', bottom: 10, left: 10, fontSize: '0.7em', color: '#555', zIndex: 100 }}>
      Tracks: {tracks.length} |
      {tracks.map(t => ` [${t.source}:${t.publication.kind}]`)}
    </div>
  );
}

function AvatarRenderer() {
  const tracks = useTracks([Track.Source.Camera, Track.Source.Microphone, Track.Source.ScreenShare]);

  const videoTrack = tracks.find(t => t.publication.kind === Track.Kind.Video);
  const audioTrack = tracks.find(t => t.publication.kind === Track.Kind.Audio);

  if (videoTrack) {
    return (
      <VideoTrack
        trackRef={videoTrack}
        className="avatar-video"
      />
    );
  }

  if (audioTrack) {
    return (
      <div className="avatar-placeholder">
        <div className="avatar-icon" style={{ animation: 'pulse 2s infinite' }}>🎙️</div>
        <span>Voice Connected</span>
        <span style={{ fontSize: '0.8rem', opacity: 0.6 }}>Avatar Video Unavailable</span>
      </div>
    );
  }

  return (
    <div className="avatar-placeholder">
      <div className="avatar-icon">🤖</div>
      <span>Connecting...</span>
    </div>
  );
}

function CustomControlBar({ userInitiatedDisconnect }: {
  userInitiatedDisconnect: React.MutableRefObject<boolean>;
}) {
  const { buttonProps } = useDisconnectButton({});

  const handleDisconnect = () => {
    userInitiatedDisconnect.current = true;
    buttonProps.onClick?.({} as React.MouseEvent<HTMLButtonElement>);
  };

  return (
    <div className="lk-control-bar">
      <TrackToggle source={Track.Source.Microphone} />
      <button
        className="lk-button lk-disconnect-button"
        onClick={handleDisconnect}
        title="Leave session"
      >
        Leave
      </button>
    </div>
  );
}

export default App;
