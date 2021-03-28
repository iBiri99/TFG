import time
import psutil
import subprocess

CMD_MOUNT = "sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y"
CMD_UMOUNT= "modprobe -r g_mass_storage"

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
	wriAnt_USB=p_USB.io_counters().write_count
	wriAnt_SMB=p_SMB.io_counters().write_count
	#process=subprocess.Popen(['fswatch','-r','--event=Updated','/mnt/usb_share'],stdout=subprocess.PIPE,universal_newlines=True)
	print("Empezamos a monitorear")
	while True:
		if p_USB.io_counters().write_count!=wriAnt_USB:
			#Si se da este caso significa que el master esta escribiendo, por lo tanto, SAMBA solo de escritura.
			print("HEMOS DETECTADO ESCRITURA POR USB")
		print(p_SMB.io_counters())
		if p_SMB.io_counters().write_count!=wriAnt_SMB:
		#if process.stdout.readline() is not None:
			#Si se da este caso significa que el esclavo esta escribiendo, por lo tanto, USB solo de escritura.
			print("HEMOS DETECTADO ESCRITURA POR SAMABA")
			#print(process.stdout.readline())
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
