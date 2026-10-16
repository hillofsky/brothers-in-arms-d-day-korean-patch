"""Minimal PPSSPP debug WebSocket reader; only request/recv/memory.read, never cpu/input/write."""
import base64,json,os,socket,struct

class WS:
    def __init__(self,port):
        self.socket=socket.create_connection(('127.0.0.1',int(port)),timeout=5)
        self.socket.settimeout(12)
        key=base64.b64encode(os.urandom(16)).decode('ascii')
        handshake=(f'GET /debugger HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n'
                   'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                   f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n'
                   'Sec-WebSocket-Protocol: debugger.ppsspp.org\r\n\r\n')
        self.socket.sendall(handshake.encode('ascii'))
        received=b''
        while b'\r\n\r\n' not in received:
            part=self.socket.recv(4096)
            if not part:raise RuntimeError('PPSSPP closed during WebSocket handshake')
            received+=part
            if len(received)>32768:raise RuntimeError('WebSocket handshake too large')
        if b' 101 ' not in received.split(b'\r\n',1)[0]:
            raise RuntimeError('WebSocket handshake refused')
        self.ticket=0

    def read_exact(self,n):
        parts=[]
        while n>0:
            r=self.socket.recv(n)
            if not r:raise RuntimeError('PPSSPP debugger disconnected')
            parts.append(r);n-=len(r)
        return b''.join(parts)

    def send_json(self,obj):
        payload=json.dumps(obj,separators=(',',':')).encode('utf-8')
        mask=os.urandom(4)
        size=len(payload)
        if size<126:header=bytes([0x81,0x80|size])
        elif size<65536:header=bytes([0x81,0x80|126])+struct.pack('!H',size)
        else:header=bytes([0x81,0x80|127])+struct.pack('!Q',size)
        self.socket.sendall(header+mask+bytes(b^mask[i%4] for i,b in enumerate(payload)))

    def pong(self,payload):
        mask=os.urandom(4)
        n=len(payload)
        if n>=126:raise ValueError('Invalid WebSocket ping payload')
        self.socket.sendall(bytes([0x8A,0x80|n])+mask+bytes(b^mask[i%4] for i,b in enumerate(payload)))

    def recv_json(self):
        parts=[];active=False
        while True:
            a,b=self.read_exact(2)
            opcode=a&0xf;final=a&0x80
            n=b&0x7f
            if n==126:n=struct.unpack('!H',self.read_exact(2))[0]
            elif n==127:n=struct.unpack('!Q',self.read_exact(8))[0]
            m=self.read_exact(4) if b&0x80 else None
            payload=self.read_exact(n) if n else b''
            if m:payload=bytes(byte^m[i%4] for i,byte in enumerate(payload))
            if opcode==8:raise RuntimeError('PPSSPP debugger sent CLOSE')
            if opcode==9:self.pong(payload);continue
            if opcode==10:continue
            if opcode==1:active=True;parts=[payload]
            elif opcode==0 and active:parts.append(payload)
            else:continue
            if final and active:
                try:return json.loads(b''.join(parts).decode('utf-8'))
                except Exception:continue

    def request(self,event,seconds=8,**params):
        allowed={'version','game.status','memory.read'}
        if event not in allowed:raise ValueError('Read-only API blocks '+event)
        self.ticket+=1
        ticket=self.ticket
        self.send_json({'event':event,'ticket':ticket,**params})
        old=self.socket.gettimeout();self.socket.settimeout(seconds)
        try:
            while True:
                response=self.recv_json()
                if response.get('ticket')!=ticket:continue
                if response.get('event')=='error':raise RuntimeError(f'{event}: {response}')
                return response
        finally:self.socket.settimeout(old)

    def close(self):
        try:self.socket.close()
        except Exception:pass


def memread(ws,address,size):
    if size<=0 or size>0x1000:raise ValueError('Each passive memory.read restricted to 4KiB')
    if not (0x08000000<=address and address+size<=0x0A000000):
        raise ValueError('Only known PSP RAM addresses allowed')
    reply=ws.request('memory.read',8,address=address,size=size,replacements=False)
    data=base64.b64decode(reply['base64'],validate=True)
    if len(data)!=size:raise RuntimeError('Incomplete memory.read')
    return data
