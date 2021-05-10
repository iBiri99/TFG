import time
import psutil
import subprocess
import os
import threading
import pyinotify
import configparser
from flask import Flask
app = Flask(__name__)


CMD_MOUNT = "sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y"
CMD_UMOUNT= "sudo modprobe -r g_mass_storage"
tiempoEspera=5
tiempoEsperaDesdeMontado=30 #En segundos
tiempoMontado=0
tiempoDespuesEscritura = True
tiempoPeriodico = True
tiempoActualizar = 5 # En minutos.

tiempoDesdeCambio=0

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
def buscarProceso(str):
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
			os.system(str) #Metemos por parametro el comando a ejecutar (Por si es lectura o lectura/escritura)
			time.sleep(2) #Tiempo para que se monte correctamente.
			print("Se ha montado el USB")
		if flagSMB is False:
			os.system("sudo systemctl start smbd")

primeravez=True
def actualizarCadaXMinutos():
	global tiempoActualizar
	global primeravez
	tiempo=tiempoActualizar*60
	threading.Timer(tiempo,actualizarCadaXMinutos).start()
	print("Ha pasado el tiempo: "+ str(tiempo))
	global tiempoDesdeCambio
	while True:
		tiempo=int(time.time())-int(tiempoDesdeCambio)
		print("El tiempo desde la ultima escritura es: "+str(tiempo))
		print(str(primeravez))
		if tiempoDesdeCambio==0 and primeravez is True:
			#No ha habido cambio
			primeravez=False
			print("UPS")
			break
		print(str(tiempo>10))
		print("QUE COÑO PASA")
		if tiempo>10:
      	# 10 segundos por si las moscas desde la ultima escritura
			os.system(CMD_UMOUNT)
			print("Usb desconectado")
			time.sleep(1)
			os.system("sudo umount -l /mnt/usb_share")
			time.sleep(1)
			print("Desmontaje realizado")
			os.system("sudo mount /mnt/usb_share")
			time.sleep(1)
			os.system(CMD_MOUNT)
			print("Montaje realizado")
			time.sleep(2)
			print("Conexion USB realizada")
			print("Cambio de Samba realizado")
			cambioSamba(True)
			time.sleep(1)
			break;
		else:
			print("Esperamos 7 segundos por la limitacion del tiempo")
			time.sleep(7) #Esperamos
		
        
    

def monitorearProceso(p_USB,p_SMB):
	#Deteccion de cambios en samba.
	y = threading.Thread(target=ControlSamba)
	y.start()
	global flag
	global tiempoMontado
	global tiempoDespuesEscritura
	global tiempoPeriodico
	global tiempoEsperaDesdeMontado
	global primeravez
	estadoMod=False
	primeravez=True
	#os.system(CMD_MOUNT)
	tiempoMontado=time.time()
	tiempoDesdeCamb=time.time()
	modoRead=False
	escrit=False
	wriAnt_USB=p_USB.io_counters().write_count
	print("Empezamos a monitorear")
	if tiempoPeriodico is True:
	    #Se va a actulizar cada X tiempo.
	    actualizarCadaXMinutos()
	while True:
		print(p_USB.io_counters())
		time.sleep(1)
		tiempoDesdeMontado=int(int(time.time()-tiempoMontado)) #Tiempo bruto desde que se ha montado
		if p_USB.io_counters().write_count==0:
			tiempoDesdeCambio=time.time()
		print("Han pasado: "+str(tiempoDesdeMontado)+"y WriANT: "+str(wriAnt_USB))
		if p_USB.io_counters().write_count!=wriAnt_USB and tiempoDesdeMontado>tiempoEsperaDesdeMontado:
			print("Escritura detectada")
			tiempoDesdeCambio=time.time()#Vamos a coger el tiempo desde la ultima deteccion de cambio de escritura.
			if not modoRead:
				#Si se da este caso significa que el master esta escribiendo, por lo tanto, SAMBA solo de escritura.
				cambioSamba(True)
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
			tiem2=int(time.time())-int(tiempoDesdeCambio)
			print("Tiempo desde el ultimo cambio: "+str(tiem2))
			if tiem2>tiempoEspera and tiempoDespuesEscritura is True: #Ya ha terminado de escribir del todo,y hemos esperado el tiempo (SI SE ELIGE ASI), volvemos a poner todo como debe.
				os.system(CMD_UMOUNT)
				print("Usb desconectado")
				os.system("sudo umount -l /mnt/usb_share")
				print("Desmontaje realizado")
				os.system("sudo mount /mnt/usb_share")
				print("Montaje realizado")
				print("Cambio de Samba realizado")
				cambioSamba(False)
				os.system("sudo systemctl restart smbd")
				p_USB,p_SMB=buscarProceso(CMD_MOUNT)
				time.sleep(2)
				tiempoMontado=time.time()
				print("Conexion USB realizada")
				escrit=False
			elif tiempoDespuesEscritura is False:
				escrit=False # Para que no siga entrando aqui.
		#Podemos detectar los cambios de samba con un notificador de deteccion de ficheros. en linux es ionify, pero hay una libreria que hace lo mismo: pionify.
		if flag == 1:
			#Desconectamos y conectamos el USB
			print("HEMOS DETECTADO UNA MODIFICACION POR SAMBA")
			time.sleep(2)
			os.system(CMD_UMOUNT) #Desconectamos el USB
			time.sleep(2)
			print("USB DESMONTADO")
			p_USB,p_SMB=buscarProceso(CMD_MOUNT)
			tiempoMontado=time.time()
			print("USB MONTADO")
			estadoMod=False
			flag=0
		elif flag == 2:
			#Se ha creado un nuevo archivo, hay que esperar hasta que se cierra, mientras, USB solo en read.
			print("HEMOS DETECTADO ESCRITURA POR SAMBA")
			time.sleep(2)
			if estadoMod is False:
				os.system(CMD_UMOUNT) #Desconectamos el USB
			time.sleep(2)
			print("USB desconectado")
			if estadoMod is False:
				p_USB,p_SMB=buscarProceso("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=1 removable=y")
				estadoMod=True
			tiempoMontado=time.time()
			print("USB conectado como solo READ")
			modoRead=True
			flag=0
		elif flag == 3:
			#Ya se ha cerrado el archivo, por lo que ya podemos volver a conectar con write.
			print("HEMOS DETECTADO CIERRE DE ARCHIVO")
			estadoMod=False
			time.sleep(2)
			os.system(CMD_UMOUNT) #Desconectamos el USB
			time.sleep(2)
			print("USB DESMONTADO")
			p_USB,p_SMB=buscarProceso(CMD_MOUNT)
			print("USB conectado como READ/WRITE")
			tiempoMontado=time.time()
			modoRead=False
			flag=0
		if flag!=0:
			#Ya hemos atendido la señal.
			flag=0
		wriAnt_USB=p_USB.io_counters().write_count

    
def principalThread():
    #Ejecutar el comando para montar.
	#Primero encontramos el proceso.
	print("Buscando procesos...")
	p_USB,p_SMB=buscarProceso(CMD_MOUNT)
	print("Procesos encontrados!")
	try:
		monitorearProceso(p_USB,p_SMB)
		time.sleep(1)
	except KeyboardInterrupt:
		os.system(CMD_UMOUNT)
		exit()
	except Exception as ex:
		print(ex)
		print("UY HA CASCADO, intentando arreglarlo.")
		p_USB,p_SMB=buscarProceso(CMD_MOUNT)
		monitorearProceso(p_USB,p_SMB)

##COSAS DE LA INTERFAZ WEB
@app.route('/inicio')
def hello_world():
    return 'Hello, World!'

###############################EL MAIN###############################
if __name__ == "__main__":
	x = threading.Thread(target=principalThread)
	x.start()
	time.sleep(5)
	app.run(debug=False,host='0.0.0.0')
