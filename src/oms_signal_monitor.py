# -------------------
# OMS SIGNAL MONITOR
# -------------------

import zmq, pickle
ctx = zmq.Context()
s = ctx.socket(zmq.SUB)
s.connect("tcp://localhost:5555")
s.setsockopt_string(zmq.SUBSCRIBE, "")
while True:
    msg = s.recv_pyobj()
    print("SIGNAL:", msg)
