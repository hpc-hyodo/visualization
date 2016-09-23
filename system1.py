# -*- coding: utf-8 -*-

import threading
import time
import datetime
import pcapy
import socket
import sys
import netifaces
from struct import *
import geoip2.database
from math import sin,cos,atan, pi
from PIL import Image
import numpy
from OpenGL.GLUT import *
from OpenGL.GL import *
from OpenGL.GLU import *



list_packets = [] # パケット情報を溜めるリスト
thread1 = None


class Packet:
	"""
	パケットを定義するクラス
	"""
	def __init__(self, addr, is_send):
		self.addr = addr       # IPアドレス
		self.is_send = is_send # 送信パケット：true, 受信パケット：false
		self.position = 0.0    # パケット可視化時の現在地
		self.lat = None        # 緯度
		self.lng = None        # 経度
		self.protocol = None   # プロトコル番号


class CaptureThread(threading.Thread):
	"""
	指定のデバイスを流れるパケットを取得するスレッド
	"""
	global list_packets
	
	# 定数
	TIMEOUT_MS = 10000
	
	def __init__(self, device):
		super(CaptureThread, self).__init__()
		self.device = device
	
	def run(self):		
		print " === start sub thread (sub class) === "
		'''
		デバイスを開く
		引数：
			device
			snaplen (maximum number of bytes to capture _per_packet_)
			promiscious mode (1 for true)
			timeout (in milliseconds)
		'''
		cap = pcapy.open_live(self.device , 65536 , 1 , self.TIMEOUT_MS)
		# パケット取得開始
		while(1) :
			(header, packet) = cap.next()
			self.parse_packet(packet)
	
	def parse_packet(self, packet):
		# イーサネットヘッダをパース
		eth_length = 14
		eth_header = packet[:eth_length]
		eth = unpack('!6s6sH' , eth_header)
		eth_protocol = socket.ntohs(eth[2])

		#Parse IP packets, IP Protocol number = 8
		if eth_protocol == 8 :
			# IPヘッダをパース
			#take first 20 characters for the ip header
			ip_header = packet[eth_length:20+eth_length]

			#now unpack them :)
			iph = unpack('!BBHHHBBH4s4s' , ip_header)

			version_ihl = iph[0]
			version = version_ihl >> 4
			ihl = version_ihl & 0xF

			iph_length = ihl * 4

			ttl = iph[5]
			protocol = iph[6]
			s_addr = socket.inet_ntoa(iph[8]);
			d_addr = socket.inet_ntoa(iph[9]);
			
			# ネットワークアダプタ(デバイス)のローカルIPアドレス
			local_ip = netifaces.ifaddresses(self.device)[2][0]['addr']
			if s_addr == local_ip:
				pkt = Packet(d_addr, True)
				print '=== IP address: %s, state: sent ===' % pkt.addr
			else:
				pkt = Packet(s_addr, False)
				print '=== IP address: %s, state: received ===' % pkt.addr
			
			pkt.protocol = protocol
			print 'protocol number: %s' % pkt.protocol
			
			# GeoIPのデータベースを読み込む
			reader = geoip2.database.Reader('/usr/local/share/GeoIP/GeoLite2-City.mmdb')
			try:
				# IPアドレスから緯度経度を取得
				res = reader.city(pkt.addr)
				pkt.lat = res.location.latitude * 0.1
				pkt.lng = res.location.longitude * 0.1
				# 取得したパケットをリストに追加
				list_packets.append(pkt)
				print 'can get latlng!'
			except:
				print 'cannot get latlng!'

class VisualizeThread(threading.Thread):
	"""
	リストのパケットをGLUTを用いて可視化するスレッド
	"""
	global list_packets, thread1
	
	# 定数
	MAP_HEIGHT = 18
	MAP_WIDTH  = 36
	MAP_DISTANCE = 20.0
	MY_LAT =  35.41 * 0.1
	MY_LNG = 139.45 * 0.1

	
	def __init__(self):
		super(VisualizeThread, self).__init__()
		self.texture = 1
		# カメラ座標(-1<=x,y,z<=1)
		self.camera_x = 0.0
		self.camera_y = 0.0
		self.camera_z = 1.0
		
		self.angle_x = pi/2
		self.angle_y = 0.0
		
		self.window = None
		
		#self.thread1 = CaptureThread('eth0')
		#self.thread1.start()
	
	def run(self):		
		print " === start sub thread (sub class) === "
		glutInitWindowPosition(100, 100)
		glutInitWindowSize(640, 480)
		glutInit(sys.argv)
		glutInitDisplayMode(GLUT_RGBA | GLUT_DEPTH | GLUT_DOUBLE)
		self.window = glutCreateWindow("Packet Viewer")
		glutDisplayFunc(self.display)
		glutReshapeFunc(self.reshape)
		glutKeyboardFunc(self.keyboard)
		glutSpecialFunc(self.keyboard)
		glutMouseFunc(self.mouse)
		glutMotionFunc(self.drag)
		glutTimerFunc(0, self.timer, 10)
		# 背景色の指定：黒
		glClearColor(0, 0, 0, 1)
		# 半透明表示
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self.texture = self.loadTexture('map.jpg')
		glutMainLoop()


	# テクスチャ画像の読み込み
	def loadTexture(self, path):
		img = Image.open(path)
		data = img.tostring()
	
		tex = glGenTextures(1)
		glPixelStorei(GL_UNPACK_ALIGNMENT,1)
		glBindTexture(GL_TEXTURE_2D, tex)
		glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP)
		glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP)
		glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
		glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
		glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,img.size[0],img.size[1],0,GL_RGB,GL_UNSIGNED_BYTE,data)
	
		return tex

	# XYZ軸の描画
	def drawXYZ(self):
		glBegin(GL_LINES)
		glColor3f(1, 0, 0)
		glVertex3f(0, 0, 0)
		glVertex3f(100, 0, 0)
	
		glColor3f(0, 1, 0)
		glVertex3f(0, 0, 0)
		glVertex3f(0, 100, 0)
	
		glColor3f(0, 0, 1)
		glVertex3f(0, 0, 0)
		glVertex3f(0, 0, 100)
		glEnd()


	# 世界地図の描画
	def drawMaps(self):
		# テクスチャマップを有効にする
		glEnable(GL_TEXTURE_2D)
		glColor4f(1, 1, 1, 1.0)
	
		glBindTexture(GL_TEXTURE_2D, self.texture)
		glBegin(GL_QUADS)
		# テクスチャ画像での位置を指定
		glTexCoord2f(1.0, 1.0)
		# 頂点座標を指定
		glVertex3f( self.MAP_WIDTH/2, self.MAP_DISTANCE/2, self.MAP_HEIGHT/2)
		glTexCoord2f(0.0, 1.0)
		glVertex3f( -self.MAP_WIDTH/2, self.MAP_DISTANCE/2,  self.MAP_HEIGHT/2)
		glTexCoord2f(0.0, 0.0)
		glVertex3f( -self.MAP_WIDTH/2, self.MAP_DISTANCE/2,  -self.MAP_HEIGHT/2)
		glTexCoord2f(1.0, 0.0)
		glVertex3f( self.MAP_WIDTH/2, self.MAP_DISTANCE/2,  -self.MAP_HEIGHT/2)
		glEnd()

		glBindTexture(GL_TEXTURE_2D, self.texture)
		glBegin(GL_QUADS)
		glTexCoord2f(1.0, 1.0)
		glVertex3f( self.MAP_WIDTH/2, -self.MAP_DISTANCE/2,  self.MAP_HEIGHT/2)
		glTexCoord2f(0.0, 1.0)
		glVertex3f( -self.MAP_WIDTH/2, -self.MAP_DISTANCE/2,  self.MAP_HEIGHT/2)
		glTexCoord2f(0.0, 0.0)
		glVertex3f( -self.MAP_WIDTH/2, -self.MAP_DISTANCE/2,  -self.MAP_HEIGHT/2)
		glTexCoord2f(1.0, 0.0)
		glVertex3f( self.MAP_WIDTH/2, -self.MAP_DISTANCE/2,  -self.MAP_HEIGHT/2)
		glEnd()
		# テクスチャマップを無効にする
		glDisable(GL_TEXTURE_2D)

	# パケットの描画
	def drawPackets(self):
		for pkt in list_packets[:]:
			protocol = pkt.protocol
			# プロトコルによって色分け
			if protocol == 6:
				glColor4f(0,1,0,0.8)
				
			elif protocol == 17:
				glColor4f(1,1,0,0.8)
				
			else:
				glColor4f(1,1,1,0.8)
				
			# 送信パケット
			if pkt.is_send == True:
				if pkt.position < 1:
					#glColor4f(1, 0, 1, 0.8)
					# パケットに見立てた円錐の描画
					theta1 = atan((pkt.lng-self.MY_LNG)/self.MAP_DISTANCE)*180/pi
					theta2 = atan((pkt.lat-self.MY_LAT)/self.MAP_DISTANCE)*180/pi
					#pkt.position = 1
					glPushMatrix()
					glTranslatef(self.MY_LNG*(1-pkt.position) + pkt.lng*pkt.position,
								self.MAP_DISTANCE/2 - self.MAP_DISTANCE*pkt.position,
								-self.MY_LAT*(1-pkt.position) - pkt.lat*pkt.position)
					glRotatef(theta1,0,0,1)
					glRotatef(theta2,1,0,0)
					glRotatef(90,1,0,0)
					glutSolidCone(0.3,1,16,1)
					glPopMatrix()
					# パケットの流れる経路の描画
					glColor4f(1, 0, 1, 0.3)
					glBegin(GL_LINES)
					glVertex3f(self.MY_LNG,  self.MAP_DISTANCE/2, -self.MY_LAT)
					glVertex3f(pkt.lng, -self.MAP_DISTANCE/2, -pkt.lat)
					glEnd()
		
				# 爆発に見立てた球の描画
				elif pkt.position > 1:
					glColor4f(1, 0, 2 - pkt.position, 2 - pkt.position)
					glPushMatrix()
					glTranslatef(pkt.lng, -self.MAP_DISTANCE/2, -pkt.lat)
					glutSolidSphere(pkt.position*3 - 3,16,16)
					glPopMatrix()
		
				pkt.position+=0.01
				if pkt.position > 2:
					list_packets.remove(pkt)
			
			# 受信パケット
			else:
				if pkt.position < 1:
					# パケットに見立てた円錐の描画
					theta1 = atan(-(pkt.lng-self.MY_LNG)/self.MAP_DISTANCE)*180/pi
					theta2 = atan(-(pkt.lat-self.MY_LAT)/self.MAP_DISTANCE)*180/pi
					#pkt.position = 1
					glPushMatrix()
					glTranslatef(self.MY_LNG*pkt.position + pkt.lng*(1-pkt.position),
								self.MAP_DISTANCE/2 - self.MAP_DISTANCE*pkt.position,
								-self.MY_LAT*pkt.position - pkt.lat*(1-pkt.position))
					glRotatef(theta1,0,0,1)
					glRotatef(theta2,1,0,0)
					glRotatef(90,1,0,0)
					glutSolidCone(0.3,1,16,1)
					glPopMatrix()
					# パケットの流れる経路の描画
					glColor4f(0, 0, 1, 0.3)
					glBegin(GL_LINES)
					glVertex3f(self.MY_LNG,  -self.MAP_DISTANCE/2, -self.MY_LAT)
					glVertex3f(pkt.lng, self.MAP_DISTANCE/2, -pkt.lat)
					glEnd()
		
				pkt.position+=0.01
				if pkt.position > 1:
					list_packets.remove(pkt)
				
				'''
					# 没になった動き
					glColor4f(0, 0, 1, 0.8)
					# パケットに見立てた円錐の描画
					theta1 = atan((pkt.lng-self.MY_LNG)/self.MAP_DISTANCE)*180/pi
					theta2 = atan((pkt.lat-self.MY_LAT)/self.MAP_DISTANCE)*180/pi
					#pkt.position = 1
					glPushMatrix()
					glTranslatef(self.MY_LNG*pkt.position + pkt.lng*(1-pkt.position),
								-self.MAP_DISTANCE/2 + self.MAP_DISTANCE*pkt.position,
								-self.MY_LAT*pkt.position - pkt.lat*(1-pkt.position))
					glRotatef(theta1,0,0,1)
					glRotatef(theta2,1,0,0)
					glRotatef(-90,1,0,0)
					glutSolidCone(0.3,1,16,1)
					glPopMatrix()
					# パケットの流れる経路の描画
					glColor4f(0, 0, 1, 0.3)
					glBegin(GL_LINES)
					glVertex3f(pkt.lng,  -self.MAP_DISTANCE/2, -pkt.lat)
					glVertex3f(self.MY_LNG, self.MAP_DISTANCE/2, -self.MY_LAT)
					glEnd()
					'''
				# 爆発に見立てた球の描画
				'''elif pkt.position > 1:
					glColor4f(0, 0, 1, 2 - pkt.position)
					glPushMatrix()
					glTranslatef(pkt.lng, self.MAP_DISTANCE/2, -pkt.lat)
					glutSolidSphere(pkt.position*3 - 3,16,16)
					glPopMatrix()
				'''
				pkt.position+=0.01
				if pkt.position > 2:
					list_packets.remove(pkt)
					#pkt.position = 0
	

	def display(self):
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

		self.lookat()

		glEnable(GL_DEPTH_TEST)
		self.drawXYZ()
		self.drawMaps()
		glDisable(GL_DEPTH_TEST)
	
		self.drawPackets()
	
	
		glutSwapBuffers()
		return


	# キーボード操作
	def keyboard(self, key, x, y):
		if key == '\033': # Escキーを押したら終了
			glutDestroyWindow(self.window)
			thread1.stop()
			sys.exit(0)
		
		# 矢印キーで視点操作
		if key == GLUT_KEY_UP and self.angle_y < pi / 2:
			self.angle_y += pi / 16
			self.camera_x = cos(self.angle_x)*cos(self.angle_y)
			self.camera_y = sin(self.angle_y)
			self.camera_z = sin(self.angle_x)*cos(self.angle_y)
		if key == GLUT_KEY_DOWN and self.angle_y > -pi / 2:
			self.angle_y += -pi / 16
			self.camera_x = cos(self.angle_x)*cos(self.angle_y)
			self.camera_y = sin(self.angle_y)
			self.camera_z = sin(self.angle_x)*cos(self.angle_y)
		if key == GLUT_KEY_LEFT:
			self.angle_x += pi / 16
			self.camera_x = cos(self.angle_x)*cos(self.angle_y)
			self.camera_y = sin(self.angle_y)
			self.camera_z = sin(self.angle_x)*cos(self.angle_y)
		if key == GLUT_KEY_RIGHT:
			self.angle_x += -pi / 16
			self.camera_x = cos(self.angle_x)*cos(self.angle_y)
			self.camera_y = sin(self.angle_y)
			self.camera_z = sin(self.angle_x)*cos(self.angle_y)
		
#	glutPostRedisplay()

	# マウス操作
	def mouse(self, button, state, x, y):
		# 左ボタン押下
			
		if(button == GLUT_LEFT_BUTTON and state == GLUT_DOWN):
			# 左ボタン押下時の座標を取得しておく
			self.mouse_x = x
			self.mouse_y = y
			return
			
		if(button == GLUT_RIGHT_BUTTON and state == GLUT_DOWN):
			# 視点のリセット
			self.mouse_x = x
			self.mouse_y = y
			
			self.camera_x = 0.0
			self.camera_y = 0.0
			self.camera_z = 1.0
			
			self.angle_x = pi/2
			self.angle_y = 0.0
			return
	
	# ドラッグ操作
	def drag(self, x, y):
		move_x = (x - self.mouse_x)/80.0
		self.angle_x += move_x
		
		move_y = (y - self.mouse_y)/80.0
		if self.angle_y + move_y < pi/2 and self.angle_y + move_y > -pi/2:
			self.angle_y += move_y
		
		self.mouse_x = x
		self.mouse_y = y
		
		self.camera_x = cos(self.angle_x)*cos(self.angle_y)
		self.camera_y = sin(self.angle_y)
		self.camera_z = sin(self.angle_x)*cos(self.angle_y)
		
		return

	def reshape(self, width, height):
		# ウィンドウ全体をビューポートにする
		glViewport(0, 0, width, height)
		# 変換行列の初期化
		glLoadIdentity()

		gluPerspective(80, width/height,1, 100 )
#		glOrtho(-width/200.0, width/200.0, -height/200.0, height/200.0, -10.0, 10.0)
		gluLookAt(self.camera_x*25, self.camera_y*25, self.camera_z*25, 0, 0, 0, 0, 1, 0)

	# 視点移動
	def lookat(self):
		glLoadIdentity()
		gluPerspective(80, glutGet( GLUT_WINDOW_WIDTH )/ glutGet( GLUT_WINDOW_HEIGHT),1, 100 )
		gluLookAt(self.camera_x*25, self.camera_y*25, self.camera_z*25, 0, 0, 0, 0, 1, 0)

	def timer(self, t):
		glutPostRedisplay()
		glutTimerFunc(t, self.timer, 10)


if __name__ == '__main__':
	# eth0を流れるパケットを取得するスレッド
	thread1 = CaptureThread('eth0')
	thread1.start()
	thread2 = VisualizeThread()
	thread2.start()
