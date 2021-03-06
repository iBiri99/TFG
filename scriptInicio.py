#IMPORTS del usb
import psutil,pyinotify,configparser
import sys
###Este archivo se ejecutara cuando no haya una configuracion hecha, esto es, en el primer inicio.

from flask import Flask
from flask_wtf import FlaskForm, CsrfProtect
from wtforms import PasswordField, DecimalField
from wtforms.validators import InputRequired
from flask import render_template, request, make_response, send_file, jsonify
import subprocess, os
import threading, time,json
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
csrf = CSRFProtect(app)

esperaAjax = 0

class wifiClase(FlaskForm):
	password=PasswordField('Contrasena', validators=[InputRequired(),])

class configuracionClase(FlaskForm):
	capacidad=DecimalField('Capacidad en GigaBytes', validators=[InputRequired(),])

class configuracionAdicional(FlaskForm):
	propagar=DecimalField('Tiempo de espera para propagar.', validators=[InputRequired(),])
	inicio=DecimalField('Tiempo de espera inicial.', validators=[InputRequired(),])
	actualizar=DecimalField('Cada cuanto actualizamos',validators=[InputRequired(),])

def Apagar():
	time.sleep(4) #Esperamos antes de apagar ejej
	os.system("sudo reboot")


##MEDIANTE ESTE METODO SE CARGARA LA PRIMERA PAGINA DE BIENVENIDA.
@app.route('/inicio')
def inicio():
	return make_response(render_template('/PrimerInicio.html'))


##GIF QUE HACE QUE SEA DETECTABLE.
@app.route('/carga')
def carga():
    return send_file("./static/load.gif", mimetype='image/gif')

##VENTANA QUE BUSCA Y MUESTRA LOS WIFIS DISPONIBLES PARA REALIZAR LA CONEXION.
@app.route('/wifi', methods=['GET','POST'])
def wifi():
	form = wifiClase()
	if form.validate_on_submit():
		#Ha contestado
		print("El wifi es: "+request.form['wifi']  +"La contrasena es "+form.password.data)
		f=open("/etc/wpa_supplicant/wpa_supplicant.conf","w")
		elwifi=request.form['wifi']
		lacontra=form.password.data
		f.write('country=ES\nctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\n\nnetwork={\nscan_ssid=1\nssid="'+elwifi+'"\npsk="'+lacontra+'"\n\n}')
		y = threading.Thread(target=Apagar)
		y.start()
		return make_response(render_template('/EsperaBusqueda.html'))
	else:
		cmd="iwlist"
		args="wlan0 scan"
		temp = subprocess.Popen("iwlist wlan0 scan | grep 'ESSID'", stdout = subprocess.PIPE,shell=True)
		output=str(temp.communicate())
		output = output.split("\n")
		output = output[0].split('\\')
		res = []
		i=0
		for line in output:
			aux=line.replace('ESSID:','')
			aux2=aux.replace('n                    ','')
			if i==0:
				res.append(aux2[24:-1])
				i+=1
			else:
				res.append(aux2[1:-1])
		return render_template('/seleccionWifi.html',wifis=res,form=form)

##AJAX PARA SABER EN QUE ESTADO SE ENCUENTRA LA INSTALACION DE TODO.
@app.route('/ajax',methods=['POST'])
@csrf.exempt
def ajax():
	if request.method == "POST":
		global esperaAjax
		return str(esperaAjax)

##VENTANA DE CONFIGURACION PRINCPIAL PARA DETERMINAR LA DIRECCION Y DEMAS.
@app.route('/configuracionDireccion',methods=['GET','POST'])
def parametros():
	form=configuracionAdicional()
	if request.method == "POST":
		elModo=request.form['modo']
		tiempoPropagar=form.propagar.data
		tiempoInicio=form.inicio.data
		tiempoActualizar=form.actualizar.data
		data = {}
		data['conf'] = []
		data['conf'].append({
		'modo': str(elModo),
		'propagar': str(tiempoPropagar),
		'inicio': str(tiempoInicio),
		'actualizar': str(tiempoActualizar)
		})
		with open('configuracion.conf', 'w') as outfile:
    			json.dump(data, outfile)
		print ("Todo hechoooooooooo")
		y = threading.Thread(target=Apagar)
		y.start()
		return "Todos lo cambios se han registrado correctamente, procedemos a reiniciar todo. Espere..."
	else:
		return render_template('/parametros.html',form=form)


##WIFI ESCOGIDO Y RENDERIZADO DE PAGINA DE ESPERA + REINCIO DE LA PLACA
@app.route('/wifi_cogido',methods=['GET','POST'])
def wifiCogido():
	form=configuracionClase()
	if form.validate_on_submit():
		#Es la vuelta del form.
		laCapacidad=form.capacidad.data
		x = threading.Thread(target=InstalacionSamba)
		x.start()
		z = threading.Thread(target=CreacionAlmacenamiento,args=(laCapacidad,))
		z.start()
		print("La capacidad cogida es: "+str(laCapacidad))
		return render_template('espera.html')
	else:
		return render_template('/primeraConfiguracion.html',form=form)

#THREAD PARA LA INSTALACION DE SAMBA Y QUE NO BLOQUEE
def InstalacionSamba():
	global esperaAjax
	os.system("sudo DEBIAN_FRONTEND=noninteractive apt-get -yq install samba") #Instalamos samba cuando llegue
	esperaAjax+=1 #Sumamos 1 cuando termin4
	print("Se ha instalado samba")

#THREAD PARA LA CREACION DEL SISTEMA DE ARCHIVOS.
def CreacionAlmacenamiento(capa):
	global esperaAjax
	capa=capa*1024
	os.system("sudo dd bs=1M if=/dev/zero of=/piusb.bin count="+str(capa))
	esperaAjax+=1
	print("YA se ha creado la imagen")
	os.system("sudo mkdosfs /piusb.bin -F 32 -I")
	os.system("sudo mkdir /mnt/usb_share") #Creamos la carpeta donde se va a montar.
	esperaAjax+=1
	linea="/piusb.bin /mnt/usb_share vfat users,umask=000 0 2"   #linea a anadir
	with open("/etc/fstab", "r+") as file:
		for line in file:
			if linea in line:
				break
		else:
			file.write(linea) #Si no esta la linea la anadimos

	linea2="dtoverlay=dwc2"
	with open("/boot/config.txt","r+") as file:
		for line in file:
			if linea2 in line:
				break # Lo ha encontrado, no hace falta a??anadirlo
		else:
			file.write(linea2)
	with open("/etc/modules","r+") as file:
		for line in file:
			if "dwc2" in line:
				break
		else:
			file.write("dwc2") #Escribir dwc2 despues de no encontrarlo.
	os.system("sudo mount -a")
	esperaAjax+=1
	print("Se ha dado formato")

###############################EMPEZAMOS CON LOS CONTROLES:######################################

#Con esta funcion iniciaremos todo el proceso de manejo del usb.
def principalThread():
	#Ejecutar el comando para montar.
	#Parsear el JSON
	with open('configuracion.conf') as json_file:
		data = json.load(json_file)
		global tiempoEspera
		global tiempoEsperaDesdeMontado
		global tiempoPeriodico
		global tiempoActualizar
		for p in data['conf']:
			#Solo hay uno.
			#p['modo']
			tiempoEspera=int(p['propagar'])
			tiempoEsperaDesdeMontado=int(p['inicio'])
			tiempoActualizar=int(p['actualizar'])
			if tiempoActualizar==0:
				tiempoPeriodico = False #No se hara una actualizacion periodica
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
		p_USB,p_SMB=buscarProceso(CMD_MOUNT)
		monitorearProceso(p_USB,p_SMB)


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
	def process_IN_UNMOUNT(self,evt):
		print("Se ha desmontado!")
		global notifier
		sys.exit()
		#notifier.loop()
		#controSamba()

#Si el flag es true, poner en modo solo lectura
def cambioSamba(flag):
	global config
	config=configparser.ConfigParser()
	config.read('/etc/samba/smb.conf')
	if not config.has_section("share"): #Comprobamos de que tengamos ese apartado.
		config.add_section("share")
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
	#os.system("smbcontrol smbd reload-config")
	os.system('sudo systemctl restart smbd')

notifier= None

def ControlSamba():
	global notifier
	handler = ModHandler()
	wm = pyinotify.WatchManager()
	notifier = pyinotify.Notifier(wm, handler)
	wdd = wm.add_watch("/mnt/usb_share", pyinotify.ALL_EVENTS,rec=True,auto_add=True)
	notifier.loop()
	print("SAMBA en interrupcion montada bien :)")


##Buscamos el proceso hasta que aparezca o keyboardInterrupt.
def buscarProceso(str):
	cambioSamba(False) #Ponemos que inicie siempre en modo escritura
	flagUSB=False #Flag que se??ala si se ha encontrado el proceso del USB
	flagSMB=False #Flag que se??ala si se ha encontrado el proceso de SAMBA
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
##Con esta funcion conseguimos que se actualize cada x segundos, en el caso de que el usuario lo indique
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
			#os.system(CMD_MOUNT)
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
	#y = multiprocessing.Process(target=ControlSamba, args=())
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
		try:
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
				if tiem2>tiempoEspera and tiempoDespuesEscritura is True and p_USB.io_counters().read_count==reaAnt_USB: #Ya ha terminado de escribir del todo,y hemos esperado el tiempo (SI SE ELIGE ASI), volvemos a poner todo como debe.
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
					#y.terminate()
					y = threading.Thread(target=ControlSamba)
					y.start()
				elif tiempoDespuesEscritura is False:
					escrit=False # Para que no siga entrando aqui.
			#Podemos detectar los cambios de samba con un notificador de deteccion de ficheros. en linux es ionify, pero hay una libreria que hace lo mismo: pionify.
			if flag == 1 and p_USB.io_counters().read_count==reaAnt_USB:
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
			elif flag == 2 and p_USB.io_counters().read_count==reaAnt_USB:
				#Se ha creado un nuevo archivo, hay que esperar hasta que se cierra, mientras, USB solo en read.
				print("HEMOS DETECTADO ESCRITURA POR SAMBA")
				time.sleep(2)
				if estadoMod is False:
					os.system(CMD_UMOUNT) #Desconectamos el USB
				time.sleep(2)
				print("USB desconectado")
				if estadoMod is False:
					p_USB,p_SMB=buscarProceso("sudo modprobe g_mass_storage file=/piusb.bin stall=0 ro=0 removable=y")
					estadoMod=True
				tiempoMontado=time.time()
				print("USB conectado como solo READ")
				modoRead=True
				flag=0
			elif flag == 3 and p_USB.io_counters().read_count==reaAnt_USB:
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
			if flag!=0 and p_USB.io_counters().read_count==reaAnt_USB:
				#Ya hemos atendido la se??al.
				flag=0
			wriAnt_USB=p_USB.io_counters().write_count # Para ver si esta escribiendo
			reaAnt_USB=p_USB.io_counters().read_count #Para ver si esta leyendo
		except Exception as ex:
			print("Reinciamos el prceso porque ha fallado :(")
			p_USB,p_SMB=buscarProceso(CMD_MOUNT)





if __name__ == "__main__":
	if os.path.isfile("configuracion.conf"): #La configuracion ya esta hecha.
		x = threading.Thread(target=principalThread)
		x.start()
		time.sleep(5)
	app.secret_key = 'llavesecreta'
	csrf = CsrfProtect(app)
	app.run(debug=False,host='0.0.0.0')
