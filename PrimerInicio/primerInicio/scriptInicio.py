###Este archivo se ejecutara cuando no haya una configuracion hecha, esto es, en el primer inicio.

from flask import Flask
from flask_wtf import FlaskForm, CsrfProtect
from wtforms import PasswordField, DecimalField
from wtforms.validators import InputRequired
from flask import render_template, request, make_response, send_file, jsonify
import subprocess, os
import threading, time
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
csrf = CSRFProtect(app)

esperaAjax = 0


class wifiClase(FlaskForm):
	password=PasswordField('Contrasena', validators=[InputRequired(),])

class configuracionClase(FlaskForm):
	capacidad=DecimalField('Capacidad en GigaBytes', validators=[InputRequired(),])

def Apagar():
	time.sleep(4) #Esperamos antes de apagar ejej
	os.system("sudo reboot")


@app.route('/inicio')
def inicio():
	return make_response(render_template('/PrimerInicio.html'))


@app.route('/carga')
def carga():
    return send_file("./static/load.gif", mimetype='image/gif')

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

@app.route('/ajax',methods=['POST'])
@csrf.exempt
def ajax():
	if request.method == "POST":
		global esperaAjax
		return str(esperaAjax) # jsonify({"estado",esperaAjax})



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

def InstalacionSamba():
	global esperaAjax
	os.system("sudo apt-get install samba") #Instalamos samba cuando llegue
	esperaAjax+=1 #Sumamos 1 cuando termin4
	print("Se ha instalado samba")

def CreacionAlmacenamiento(capa):
	global esperaAjax
	capa=capa*1024
	os.system("sudo dd bs=1M if=/dev/zero of=/piusb.bin count="+str(capa))
	esperaAjax+=1
	print("YA se ha creado la imagen")
	os.system("sudo mkdosfs /piusb.bin -F 32 -I")
	esperaAjax+=1
	print("Se ha dado formato")

if __name__ == "__main__":
	app.secret_key = 'llavesecreta'
	csrf = CsrfProtect(app)
	app.run(debug=False,host='0.0.0.0')
