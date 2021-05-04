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
				print("Proceso de almacenamiento encontrado")
			elif proc.name() == "smbd":
				procSMB = proc
				flagSMB=True
				print("Proceso de samba encontrado")
			if flagUSB and flagSMB:
				return procUSB,procSMB
		if flagUSB is False:
			os.system(CMD_MOUNT)
			time.sleep(2) #Tiempo para que se monte correctamente.
			print("Se ha montado el USB")
		if flagSMB is False:
			os.system("sudo systemctl start smbd")


def monitorearProceso(p_USB,p_SMB):
	#Deteccion de cambios en samba.
	x = threading.Thread(target=ControlSamba)
	x.start()
	global flag
	global tiempoMontado
	#os.system(CMD_MOUNT)
	tiempoMontado=time.time()
	tiempoDesdeCero=time.time()
	start=time.time()
	modoRead=False
	escrit=False
	wriAnt_USB=p_USB.io_counters().write_count
	print("Empezamos a monitorear")
	tiemtotal=0
	while True:
		print(p_USB.io_counters())
		time.sleep(1)
		if p_USB.io_counters().write_count==0:
			tiempoDesdeCero=time.time()
		if p_USB.io_counters().write_count!=wriAnt_USB and wriAnt_USB>20:
			start = time.time() #Vamos a coger el tiempo desde la ultima deteccion de cambio de escritura.
			print("Escritura detectada")
			tiempomon=int(tiempoMontado)-int(start)
			tiempoDesdeCero=time.time()
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
					time.sleep(2) #Comprobamos cada segundo si ha terminado.
				print("Proceso USB: "+p_USB.name())
		elif escrit is True: #Vamos a mirar si el temporizador lleva mas de x segundos
			global tiempoEspera
			print("El tiempo de inicio es: "+str(start)+" tiempo de espera "+str(tiempoEspera))
			tiem=int(time.time())-int(start)
			tiem2=int(time.time())-int(tiempoDesdeCero)
			#if tiem2<tiempoEspera:
			#	escrit=False
			#	cambioSamba(False)
			print("Tiempo entre empezar: "+str(tiem)+" tiempo desde el principio: "+str(tiem2))
			if tiem>tiempoEspera and tiem2>tiempoEspera: #Ya ha terminado de escribir del todo,y hemos esperado el tiempo, volvemos a poner todo como debe.
				print("Ha entrado aquiiiiiiiiiiiiiiiiiiiiii")
				#os.system(CMD_UMOUNT)
				print("Usb desconectado")
				os.system("sudo umount /mnt/usb_share")
				print("Desmontaje realizado")
				os.system("sudo mount /mnt/usb_share")
				print("Montaje realizado")
				#os.system(CMD_MOUNT) #Conectamos el USB
				if p_USB is None:
					p_USB,p_SMB=buscarProceso()
				time.sleep(2)
				print("Conexion USB realizada")
				print("Cambio de Samba realizado")
				cambioSamba(False)
				escrit=False
		#Podemos detectar los cambios de samba con un notificador de deteccion de ficheros. en linux es ionify, pero hay una libreria que hace lo mismo: pionify.
		if flag == 1:
			#Desconectamos y conectamos el USB
			print("HEMOS DETECTADO UNA MODIFICACION POR SAMBA")
			os.system(CMD_UMOUNT) #Desconectamos el USB
			print("USB DESMONTADO")
			os.system(CMD_MOUNT) #Conectamos para que se actualicen los datos. 
			print("USB MONTADO")
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
			os.system(CMD_UMOUNT) #Desconectamos el USB
			print("USB DESMONTADO")
			os.system(CMD_MOUNT) 
			print("USB conectado como READ/WRITE")
			tiempoMontado=time.time()
			modoRead=False
			flag=0
		if flag!=0:
			p_USB,p_SMB=buscarProceso()
			flag=0
		wriAnt_USB=p_USB.io_counters().write_count


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
		os.system(CMD_UMOUNT)
		exit()
	except Exception as ex:
		print(ex)
		p_USB,p_SMB=buscarProceso()
		monitorearProceso(p_USB,p_SMB)
