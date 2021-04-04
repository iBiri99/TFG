import time
import psutil
import subprocess
import os
import threading
import pyinotify

CMD_MOUNT = "sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y"
CMD_UMOUNT= "modprobe -r g_mass_storage"

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
		

def ControlSamba():
	handler = ModHandler()
	wm = pyinotify.WatchManager()
	notifier = pyinotify.Notifier(wm, handler)
	wdd = wm.add_watch("/mnt/usb_share", pyinotify.ALL_EVENTS)
	notifier.loop()


##Buscamos el proceso hasta que aparezca o keyboardInterrupt.
def buscarProceso():
	flagUSB=False #Flag que señala si se ha encontrado el proceso del USB
	flagSMB=False #Flag que señala si se ha encontrado el proceso de SAMBA
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
		if not flagSMB:
			os.system("sudo systemctl start smbd")


def monitorearProceso(p_USB,p_SMB):
	#Deteccion de cambios en samba.
	x = threading.Thread(target=ControlSamba)
	x.start()
	global flag
	global flagSMBterminado
	modoRead=False
	wriAnt_USB=p_USB.io_counters().write_count
	print("Empezamos a monitorear")
	while True:
		if p_USB.io_counters().write_count!=wriAnt_USB:
			#Si se da este caso significa que el master esta escribiendo, por lo tanto, SAMBA solo de escritura.
			print("HEMOS DETECTADO ESCRITURA POR USB")
			os.system("sudo systemctl stop smbd")
			print("Paramos samba")
			#Primero determinar cuando ha terminado de escribir:
			print("Comprobacion que esta escrbiendo"+str(p_USB.io_counters().write_count)+" "+str(wriAnt_USB))
			while p_USB.io_counters().write_count!=wriAnt_USB:
				print("Escribiendo...")
				wriAnt_USB=p_USB.io_counters().write_count
				time.sleep(1) #Comprobamos cada segundo si ha terminado.
			print("Ha parado de escrbir")
			os.system("sudo modprobe -r g_mass_storage") #Cuando ya ha terminado desconectamos y volvemos a conectar el usb
			print("Usb desconectado")
			os.system("sudo umount /mnt/usb_share")
			print("Desmontaje realizado")
			os.system("sudo mount /mnt/usb_share")
			print("Montaje realizado")
			os.system("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y") 
			print("Conexion USB realizada")
			os.system("sudo systemctl start smbd")
			print("Samba en marcha")
			p_USB,p_SMB=buscarProceso()
		#Podemos detectar los cambios de samba con un notificador de deteccion de ficheros. en linux es ionify, pero hay una libreria que hace lo mismo: pionify.
		if flag == 1:
			#Desconectamos y conectamos el USB
			print("HEMOS DETECTADO UNA MODIFICACION POR SAMBA")
			os.system("sudo modprobe -r g_mass_storage") #Desconectamos el USB
			os.system("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y") 
			flag=0
		elif flag == 2:
			#Se ha creado un nuevo archivo, hay que esperar hasta que se cierra, mientras, USB solo en read.
			print("HEMOS DETECTADO ESCRITURA POR SAMBA")
			os.system("sudo modprobe -r g_mass_storage") #Desconectamos el USB
			print("USB desconectado")
			os.system("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=1 removable=y") 
			print("USB conectado como solo READ")
			flag=0
		elif flag == 3:
			#Ya se ha cerrado el archivo, por lo que ya podemos volver a conectar con write.
			os.system("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y") 
			print("USB conectado como READ/WRITE")
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
