import time
import psutil
import subprocess
import os
import threading
import pyionitify

CMD_MOUNT = "sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y"
CMD_UMOUNT= "modprobe -r g_mass_storage"

class ModHandler(pyinotify.ProcessEvent):
    # evt has useful properties, including pathname
    def process_IN_CLOSE_WRITE(self, evt):
            print("HA HECHO ALGO")



def pararProceso():
	os.system("sudo systemctl stop smbd")


##Buscamos el proceso hasta que aparezca o keyboardInterrupt.
def buscarProceso():
	flag1=False #Flag que señala si se ha encontrado el proceso del USB
	flag2=False #Flag que señala si se ha encontrado el proceso de SAMBA
	while True:
		for proc in psutil.process_iter():
			if proc.name() == "file-storage":
				procUSB = proc
				flag1=True
			elif proc.name() == "smbd":
				procSMB = proc
				flag2=True
			if flag1 and flag2:
				return procUSB,procSMB


def monitorearProceso(p_USB,p_SMB):
	#Deteccion de cambios en samba.
	handler = ModHandler()
	wm = pyinotify.WatchManager()
	notifier = pyinotify.Notifier(wm, handler)
	wdd = wm.add_watch("/mnt/usb_share", pyinotify.ALL_EVENTS)
	notifier.loop()
	
	wriAnt_USB=p_USB.io_counters().write_count
	wriAnt_SMB=p_SMB.io_counters().write_count
	#process=subprocess.Popen(['fswatch','-r','--event=Updated','/mnt/usb_share'],stdout=subprocess.PIPE,universal_newlines=True)
	print("Empezamos a monitorear")
	while True:
		if p_USB.io_counters().write_count!=wriAnt_USB:
			#Si se da este caso significa que el master esta escribiendo, por lo tanto, SAMBA solo de escritura.
			print("HEMOS DETECTADO ESCRITURA POR USB")
			#Primero paramos el servidor samba o lo ponemos en modo read only para evitar problemas de corrupcion.
			#x = threading.Thread(target=pararProceso)
			#x.start()
			os.system("sudo systemctl stop smbd")
			print("Paramos samba")
			#out = subprocess.run(['service', 'smbd', 'stop'],stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
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
		#print(p_SMB.io_counters())
		#Podemos detectar los cambios de samba con un notificador de deteccion de ficheros. en linux es ionify, pero hay una libreria que hace lo mismo: pionify.
		if p_SMB.io_counters().write_count!=wriAnt_SMB:
			#Si se da este caso significa que el esclavo esta escribiendo, por lo tanto, USB solo de escritura.
			print("HEMOS DETECTADO ESCRITURA POR SAMBA")
			os.system("sudo modprobe -r g_mass_storage") #Desconectamos el USB
			print("USB desconectado")
			os.system("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=1 removable=y") 
			print("USB conectado como solo READ")
			#Comprobar cuanto tiempo esta escribiendo
			
		wriAnt_USB=p_USB.io_counters().write_count
		wriAnt_SMB=p_SMB.io_counters().write_count





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
		p1=buscarProceso()
		monitorearProceso(p1)
