import time
import psutil
import subprocess
import os
import threading
import pyinotify
import configparser

CMD_MOUNT = "sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y"
CMD_UMOUNT= "modprobe -r g_mass_storage"
tiempoEspera=5
tiempoMontado=0

flag=0

class ModHandler(pyinotify.ProcessEvent):
	# evt has useful properties, including pathname
	def process_IN_MODIFY(self, evt):
		global flag
		print("Modificado")
		flag=1
	def process_IN_CREATE(self, evt):
		global flag
		print("Creado")
		flag=2
	def process_IN_DELETE(self, evt):
		global flag
		print("Eliminado")
		flag=1
	def process_IN_CLOSE_WRITE(self,evt):
		global flag
		print("Se ha cerrado")
		flag=3

#Si el flag es true, poner en modo solo lectura
def cambioSamba(flag):
	global config
	config=configparser.ConfigParser()
	config.read('/etc/samba/smb.conf')
	if flag is True:
		config['share']={"comment" : "Raspberry pi prueba",
		"path" : "/mnt/usb_share",
		"browsable" : "yes",
		"guest ok" : "yes",
		"read only" : "yes",
		"create mask" : "0700"}
	else:
		config['share']={"comment" : "Raspberry pi prueba",
		"path" : "/mnt/usb_share",
		"browsable" : "yes",
		"guest ok" : "yes",
		"read only" : "no",
		"create mask" : "0700"}
	with open('/etc/samba/smb.conf', 'w') as configfile:
		config.write(configfile)
	os.system("smbcontrol smbd reload-config")

def ControlSamba():
	handler = ModHandler()
	wm = pyinotify.WatchManager()
	notifier = pyinotify.Notifier(wm, handler)
	wdd = wm.add_watch("/mnt/usb_share", pyinotify.ALL_EVENTS)
	notifier.loop()


##Buscamos el proceso hasta que aparezca o keyboardInterrupt.
def buscarProceso():
	cambioSamba(False) #Ponemos que inicie siempre en modo escritura
	flagUSB=False #Flag que señala si se ha encontrado el proceso del USB
	flagSMB=False #Flag que señala si se ha encontrado el proceso de SAMBA
	os.system(CMD_UMOUNT)
	while True:
		for proc in psutil.process_iter():
			if proc.name() == "file-storage":
				procUSB = proc
				flagUSB=True
			elif proc.name() == "smbd":
				procSMB = proc
				flagSMB=True
			if flagUSB and flagSMB:
				return procUSB,procSMB
		if not flagUSB:
			os.system("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y") 
			time.sleep(2) #Tiempo para que se monte correctamente.
		if not flagSMB:
			os.system("sudo systemctl start smbd")


def monitorearProceso(p_USB,p_SMB):
	#Deteccion de cambios en samba.
	x = threading.Thread(target=ControlSamba)
	x.start()
	global flag
	global tiempoMontado
	tiempoMontado=time.time()
	start=time.time()
	modoRead=False
	escrit=False
	wriAnt_USB=p_USB.io_counters().write_count
	print("Empezamos a monitorear")
	while True:
		print(p_USB.io_counters())
		time.sleep(1)
		if p_USB.io_counters().write_count!=wriAnt_USB:
			start = time.time() #Vamos a coger el tiempo desde la ultima deteccion de cambio de escritura.
			print("Escritura detectada")
			if not modoRead:
				#Si se da este caso significa que el master esta escribiendo, por lo tanto, SAMBA solo de escritura.
				cambioSamba(True)
				aux=p_USB.io_counters().write_count-wriAnt_USB
				rec=p_USB.io_counters().write_count
				escrit=True
				#Primero determinar cuando ha terminado de escribir:
				print("Comprobacion que esta escrbiendo"+str(p_USB.io_counters().write_count)+" "+str(wriAnt_USB))
				while p_USB.io_counters().write_count!=rec:
					rec=p_USB.io_counters().write_count
					print("Escribiendo...")
					#wriAnt_USB=p_USB.io_counters().write_count
					time.sleep(2) #Comprobamos cada segundo si ha terminado.
				print("Ha parado de escrbir")
				#Solo conectamos y desconectamos cuando la escritura ha sido lo suficiente grande:
				print("El valor de aux es: "+str(aux)+" y el de rec: "+str(rec))
				aux=p_USB.io_counters().write_count-wriAnt_USB
				print("El tiempo desde la ultima conexion es: "+ str(int(time.time())-int(tiempoMontado)))
				if aux>2 and time.time()-tiempoMontado>10.0:
					os.system(CMD_UMOUNT) #Cuando ya ha terminado desconectamos y volvemos a conectar el usb
					print("Usb desconectado")
					os.system("sudo umount /mnt/usb_share")
					print("Desmontaje realizado")
					os.system("sudo mount /mnt/usb_share")
					print("Montaje realizado")
					os.system(CMD_MOUNT)
					print("Conexion USB realizada")
					tiempoMontado=time.time()
					time.sleep(2) #Dar tiempo a que se hagan las escrituras correctamente.
				p_USB,p_SMB=buscarProceso()
		elif escrit is True: #Vamos a mirar si el temporizador lleva mas de x segundos
			act=time.time()
			global tiempoEspera
			print("El tiempo de inicio es: "+str(start)+" Y el actual: "+ str(act)+" tiempo de espera "+str(tiempoEspera))
			tiem=int(act)-int(start)
			if tiem>tiempoEspera:
				print("Cambio de Samba realizado")
				cambioSamba(False)
				escrit=False
		#Podemos detectar los cambios de samba con un notificador de deteccion de ficheros. en linux es ionify, pero hay una libreria que hace lo mismo: pionify.
		if flag == 1:
			#Desconectamos y conectamos el USB
			print("HEMOS DETECTADO UNA MODIFICACION POR SAMBA")
			os.system(CMD_UMOUNT) #Desconectamos el USB
			os.system("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y") 
			flag=0
		elif flag == 2:
			#Se ha creado un nuevo archivo, hay que esperar hasta que se cierra, mientras, USB solo en read.
			print("HEMOS DETECTADO ESCRITURA POR SAMBA")
			os.system(CMD_UMOUNT) #Desconectamos el USB
			print("USB desconectado")
			os.system("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=1 removable=y") 
			print("USB conectado como solo READ")
			modoRead=True
			flag=0
		elif flag == 3:
			#Ya se ha cerrado el archivo, por lo que ya podemos volver a conectar con write.
			os.system("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y") 
			print("USB conectado como READ/WRITE")
			tiempoMontado=time.time()
			modoRead=False
			flag=0
		if flag!=0:
			p_USB,p_SMB=buscarProceso()
			flag=0
		wriAnt_USB=p_USB.io_counters().write_count
		#wriAnt_SMB=p_SMB.io_counters().write_count


if __name__ == "__main__":
	#Ejecutar el comando para montar.
	#Primero encontramos el proceso.
	print("Buscando procesos...")
	p_USB,p_SMB=buscarProceso()
	print("Procesos encontrados!")
	#os.system(CMD_MOUNT)
	try:
		monitorearProceso(p_USB,p_SMB)
		#p.io_counter().write_count ## Podemos ver el numero de escrituras que tiene.
		#time.sleep(1)
	except KeyboardInterrupt:
		exit()
	except:
		p_USB,p_SMB=buscarProceso()
		monitorearProceso(p_USB,p_SMB)
