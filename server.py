"""
Aaron Chao
September 20, 2018

An implementation of a chatroom server
Supports:
 - broadcasting messages to other peer servers via multithreading
 - detecting loss of connection with other peer servers
 - detecting connection by other peer servers
"""

import threading
import socket
import server
import time
import sys
import select

HOST = '127.0.0.1'
MASTER_PORT = 10000
SERVER_PORT = 20000
RECEIVE_SIZE = 4096

class Socket(threading.Thread):
    def __init__(self, server, port):
        threading.Thread.__init__(self)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
        self.socket.setblocking(1)
        self.port = port
        self.server = server

class ListenSocket(Socket):
    def __init__(self, server, listen_port):
        super(ListenSocket, self).__init__(server, listen_port)
        self.socket.bind((HOST, self.port))
        self.socket.listen(5)

    def run(self):
        while True:
            conn, addr = self.socket.accept()
            print('Server ' + str(self.server.server_id) + ' connected by ' + str(addr))
            conn.send(str(self.server.server_id))
            remoteServer = conn.recv(RECEIVE_SIZE)
            self.server.addAliveServer(remoteServer)
            self.server.makeConnection(conn, remoteServer)

class ConnectSocket(Socket):
    def __init__(self, server, connect_port):
        super(ConnectSocket, self).__init__(server, connect_port)

    def run(self):
        try:
            self.socket.connect((HOST, self.port))
            self.socket.send(str(self.server.server_id))
            self.remoteServer = self.socket.recv(RECEIVE_SIZE)
            self.server.addAliveServer(self.remoteServer)
            self.server.connections.append(self)
            print('Server ' + str(self.server.server_id) + ' connected to server:' + str(self.port - SERVER_PORT))
            while True:
                data = self.socket.recv(RECEIVE_SIZE)
                if data == '':
                    self.server.removeAliveServer(self.remoteServer)
                    break
                messages = data.split('\n')
                print('Server ' + str(self.server.server_id) + ' received: ' + str(messages))
                for message in messages:
                    if message != '':
                        print('Server ' + str(self.server.server_id) + ' received from server: ' + message)
                        self.server.addMessage(message)
        except:
            print('Server ' + str(self.server.server_id) + ' failed to connect to server: ' + str(self.port - SERVER_PORT))

    def sendMessage(self, msg):
        self.socket.send(msg)

class MasterSocket(ListenSocket):
    def __init__(self, server, listen_port):
        super(MasterSocket, self).__init__(server, listen_port)

    def run(self):
        self.conn, addr = self.socket.accept()
        print('Server ' + str(self.server.server_id) + ' connected by master')
        while True:
            data = self.conn.recv(RECEIVE_SIZE)
            commands = data.split('\n')
            print('Server ' + str(self.server.server_id) + ' received: ' + str(commands))
            for command in commands:
                if command != '':
                    print('Server ' + str(self.server.server_id) + ' received command from master: ' + command)
                    self.server.masterHandler(command)

    def sendMessage(self, msg):
        self.conn.send(msg)

class Connection(threading.Thread):
    def __init__(self, server, conn, remoteServer):
        threading.Thread.__init__(self)
        self.server = server
        self.conn = conn
        self.remoteServer = remoteServer

    def run(self):
        try:
            while True:
                data = self.conn.recv(RECEIVE_SIZE)
                if data == '':
                    self.server.removeAliveServer(self.remoteServer)
                    break
                messages = data.split('\n')
                print('Server ' + str(self.server.server_id) + ' received: ' + str(messages))
                for message in messages:
                    if message != '':
                        print('Server ' + str(self.server.server_id) + ' received data from server: ' + str(message))
                        self.server.addMessage(message)
        except:
            print('Server ' + str(self.server.server_id) + ' received broken connection')

    def sendMessage(self, msg):
        self.conn.send(msg)

class Server(threading.Thread):
    def __init__(self, server_id, n, port):
        threading.Thread.__init__(self)
        self.server_id = server_id
        self.messages = []
        self.connections = []
        self.serversAlive = []
        self.serversAlive.append(str(server_id))

        self.masterConnection = MasterSocket(self, port)
        self.acceptSocket = ListenSocket(self, SERVER_PORT + self.server_id)
        print('Server ' + str(self.server_id) + ' started')
        self.masterConnection.start()
        self.connectToServers()
        self.acceptSocket.start()

    def connectToServers(self):
        for i in range(n):
            if self.server_id != i:
                connectSocket = ConnectSocket(self, SERVER_PORT + i)
                connectSocket.start()

    def addMessage(self, msg):
        self.messages.append(msg)

    def addAliveServer(self, server_id):
        print('Server ' + str(self.server_id) + ' - Adding ' + server_id + ' to alive servers')
        self.serversAlive.append(server_id)

    def removeAliveServer(self, server_id):
        print('Server ' + str(self.server_id) + ' - Removing ' + server_id + ' from alive servers')
        self.serversAlive.remove(server_id)

    def makeConnection(self, conn, remoteServer):
        listener = Connection(self, conn, remoteServer)
        self.connections.append(listener)
        listener.start()

    def removeConnection(self, conn):
        self.listeners.remove(conn)

    def masterHandler(self, data):
        if data[0:3] == 'get':
            msgs = []
            for msg in self.messages:
                msgs.append(msg.rstrip())
            m = ','.join(msgs)
            response = str(len(m) + 9) + '-messages ' + m + '\n'
            print('Server ' + str(self.server_id) + ' sending to master: ' + response)
            self.masterConnection.sendMessage(response)
        elif data[0:5] == 'alive':
            servers = self.serversAlive
            servers.sort()
            s = ','.join(servers)
            response = str(len(s) + 6) + '-alive '+ s + '\n'
            print('Server ' + str(self.server_id) + ' sending to master: ' + response)
            self.masterConnection.sendMessage(response)
        else:
            msg = data[10:]
            self.messages.append(msg)
            for connection in self.connections:
                print('Server ' + str(self.server_id) + ' sending data to another server')
                connection.sendMessage(msg + '\n')

if __name__ == '__main__':
    server_id = int(sys.argv[1])
    n = int(sys.argv[2])
    port = int(sys.argv[3])
    server = Server(server_id, n, port)
