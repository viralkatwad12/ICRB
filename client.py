# client.py
import argparse
import asyncio
import json
import aiohttp
import cv2
import time

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, RTCConfiguration, RTCIceServer, VideoStreamTrack
import av

# Signaling server endpoint URL
SIGNALING_SERVER = "ws://localhost:8080/ws"

# A custom VideoStreamTrack that captures frames from your webcam using OpenCV.
class VideoCameraTrack(VideoStreamTrack):
    """
    A video track that captures video from the default webcam.
    """
    def __init__(self):
        super().__init__()  # Initialize base class
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open webcam.")

    async def recv(self):
        # Control the frame rate (e.g., 30 fps)
        await asyncio.sleep(1/30)
        ret, frame = self.cap.read()
        if not ret:
            return

        # Convert the frame to an av.VideoFrame
        video_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = int(time.time() * 90000)
        video_frame.time_base = 1/90000
        return video_frame

    def stop(self):
        self.cap.release()
        super().stop()

async def run_offer(pc, ws, target_id):
    # Create an SDP offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    
    # Send the offer through the signaling server to the target peer
    message = {
        "type": "signal",
        "to": target_id,
        "data": {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }
    }
    await ws.send_json(message)
    print("Offer sent")

async def run_answer(pc, ws, from_id, offer_data):
    # Set the remote description from the received offer
    offer = RTCSessionDescription(sdp=offer_data["sdp"], type=offer_data["type"])
    await pc.setRemoteDescription(offer)
    
    # Create an SDP answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    
    # Send the answer back to the offerer
    message = {
        "type": "signal",
        "to": from_id,
        "data": {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }
    }
    await ws.send_json(message)
    print("Answer sent")

async def signaling_loop(pc, client_mode, target_id):
    """
    Opens a WebSocket connection to the signaling server and handles incoming messages.
    """
    session = aiohttp.ClientSession()
    async with session.ws_connect(SIGNALING_SERVER) as ws:
        print("Connected to signaling server.")

        # If operating as an offerer, wait briefly and then send an offer.
        if client_mode == "offer":
            await asyncio.sleep(1)  # Small delay to ensure connection setup
            await run_offer(pc, ws, target_id)

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data["type"] == "id":
                    # The server assigns an ID to this client.
                    client_id = data["id"]
                    print(f"My client ID is {client_id}")
                elif data["type"] == "signal":
                    sender_id = data.get("from")
                    signal_data = data.get("data")
                    if "sdp" in signal_data:
                        if signal_data["type"] == "offer":
                            print("Received offer")
                            await run_answer(pc, ws, sender_id, signal_data)
                        elif signal_data["type"] == "answer":
                            print("Received answer")
                            answer = RTCSessionDescription(sdp=signal_data["sdp"], type=signal_data["type"])
                            await pc.setRemoteDescription(answer)
                    elif "candidate" in signal_data:
                        # Handle ICE candidate (if implemented)
                        candidate = RTCIceCandidate(
                            candidate=signal_data["candidate"],
                            sdpMid=signal_data.get("sdpMid"),
                            sdpMLineIndex=signal_data.get("sdpMLineIndex")
                        )
                        await pc.addIceCandidate(candidate)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break

    await session.close()

async def main(mode, target_id):
    # Create a new RTCPeerConnection with a STUN server (for ICE gathering)
    configuration = RTCConfiguration(
        iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
    )
    pc = RTCPeerConnection(configuration=configuration)

    # Add the local video track (and optionally an audio track if needed)
    video_track = VideoCameraTrack()
    pc.addTrack(video_track)
    
    # When a new ICE candidate is gathered, you can send it via signaling.
    @pc.on("icecandidate")
    async def on_icecandidate(candidate):
        if candidate:
            # In a full implementation, forward the candidate to the peer.
            # For brevity, this example only prints the candidate.
            print("New ICE candidate:", candidate)

    # Start the signaling loop (this will run indefinitely)
    await signaling_loop(pc, mode, target_id)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P2P Video/Voice Call Client")
    parser.add_argument("mode", choices=["offer", "answer"], help="Run as offerer or answerer")
    parser.add_argument("--target", required=True, help="Target client ID to connect to")
    args = parser.parse_args()

    asyncio.run(main(args.mode, args.target))
