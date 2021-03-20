import time
import psutil

CMD_MOUNT = "sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y"
CMD_UMOUNT= "modprobe -r g_mass_storage"

if __name__ == "__main__":
	#Ejecutar el comando para montar.
	#os.system(CMD_MOUNT)
	while True:
		print("Procesos")
		for p in psutil.process_iter():
			if p.name() == "file-storage":
				print(p)
		#time.sleep(1)
