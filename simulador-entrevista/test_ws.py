import asyncio
import json
import websockets

async def main():
    uri = 'ws://127.0.0.1:8000/ws'
    try:
        async with websockets.connect(uri) as ws:
            print('connected')
            await ws.send(json.dumps({'type':'new','token':'invalid','job_session_id':'x'}))
            msg = await ws.recv()
            print('recv', msg)
    except Exception as e:
        print('error', type(e).__name__, e)

if __name__ == '__main__':
    asyncio.run(main())
