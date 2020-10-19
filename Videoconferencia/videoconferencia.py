# This Python file uses the following encoding: utf-8
import sys,gi
from PySide2.QtWidgets import QApplication, QMainWindow
from ui_mainwindow import Ui_MainWindow
from PySide2.QtWidgets import QMessageBox

gi.require_version('Gst','1.0')
gi.require_version('GstVideo','1.0')

from gi.repository import Gst, GstVideo

def on_pad_added(rtpbin, pad, pipeline,puerto_rtcp_1,puerto_rtcp_2,ip_destino):
    name = pad.get_name()
    depay = None
    if name.startswith('recv_rtp_src_0'):
        # Sesión de vídeo
        depay = pipeline.get_by_name('rtph264depay')
        rtcp = Gst.ElementFactory.make('udpsink')
        rtcp.set_property('host',ip_destino)
        rtcp.set_property('port',int(puerto_rtcp_1))
        rtcp.set_property('sync','false')
        rtcp.set_property('async','false')
        pipeline.add(rtcp)
        rtpbin.link_pads('send_rtcp_src_0',rtcp,'sink')
    elif name.startswith('recv_rtp_src_1'):
        # Sesión de audio
        depay = pipeline.get_by_name('rtpmp4adepay')
        rtcp = Gst.ElementFactory.make('udpsink')
        rtcp.set_property('host',ip_destino)
        rtcp.set_property('port',int(puerto_rtcp_2))
        rtcp.set_property('sync','false')
        rtcp.set_property('async','false')
        pipeline.add(rtcp)
        rtpbin.link_pads('send_rtcp_src_1',rtcp,'sink')
    if depay:
        pad_sink = depay.sinkpads[0]
        pad.link(pad_sink)

def h264_recv(pipeline,rtpbin,puerto_rtp):
    udpsrc = Gst.ElementFactory.make('udpsrc')
    udpsrc.set_property('port',int(puerto_rtp))
    caps = Gst.Caps.from_string('application/x-rtp, \
                             media=video, clock-rate=90000, \
                             encoding-name=H264')
    udpsrc.set_property('caps',caps)
    pipeline.add(udpsrc)
    rtph264depay = Gst.ElementFactory.make('rtph264depay','rtph264depay')
    pipeline.add(rtph264depay)
    queue = Gst.ElementFactory.make('queue')
    pipeline.add(queue)
    avdec_h264 = Gst.ElementFactory.make('avdec_h264')
    pipeline.add(avdec_h264)
    videoconvert = Gst.ElementFactory.make('videoconvert')
    pipeline.add(videoconvert)
    autovideosink = Gst.ElementFactory.make('autovideosink')
    pipeline.add(autovideosink)
    l1 = udpsrc.link_pads('src',rtpbin,'recv_rtp_sink_0')
    l2 = rtph264depay.link(queue)
    l3 = queue.link(avdec_h264)
    l4 = avdec_h264.link(videoconvert)
    l5 = videoconvert.link(autovideosink)
    return l1 and l2 and l3 and l4 and l5

def aac_recv(pipeline,rtpbin,puerto_rtp,volumen):
    udpsrc = Gst.ElementFactory.make('udpsrc')
    udpsrc.set_property('port',int(puerto_rtp))
    caps = Gst.Caps.from_string('application/x-rtp, \
                             media=audio,encoding-name=MP4A-LATM, \
                             clock-rate=48000,config=40002320adca00')
    udpsrc.set_property('caps',caps)
    pipeline.add(udpsrc)
    rtpmp4adepay = Gst.ElementFactory.make('rtpmp4adepay','rtpmp4adepay')
    pipeline.add(rtpmp4adepay)
    queue = Gst.ElementFactory.make('queue')
    pipeline.add(queue)
    avdec_aac = Gst.ElementFactory.make('avdec_aac')
    pipeline.add(avdec_aac)
    audioconvert = Gst.ElementFactory.make('audioconvert')
    pipeline.add(audioconvert)
    volume = Gst.ElementFactory.make('volume', 'volumen')
    volume.set_property('volume', volumen)
    pipeline.add(volume)
    autoaudiosink = Gst.ElementFactory.make('autoaudiosink')
    pipeline.add(autoaudiosink)
    l1 = udpsrc.link_pads('src',rtpbin,'recv_rtp_sink_1')
    l2 = rtpmp4adepay.link(queue)
    l3 = queue.link(avdec_aac)
    l4 = avdec_aac.link(audioconvert)
    l5 = audioconvert.link(volume)
    l6 = volume.link(autoaudiosink)
    return l1 and l2 and l3 and l4 and l5


def x264_send(pipeline,rtpbin,puerto_rtp,puerto_rtcp,ip_destino,resolucion,fps,bitrate_video,drop_prob):
    video = Gst.ElementFactory.make('v4l2src')
    pipeline.add(video)
    convert = Gst.ElementFactory.make('videoconvert')
    pipeline.add(convert)

    rate = Gst.ElementFactory.make('videorate')
    pipeline.add(rate)
    filter = Gst.ElementFactory.make('capsfilter', 'filter_video')

    width = resolucion.split('x')[0]
    height = resolucion.split('x')[1]
    text_filter = 'video/x-raw,width={}, \
                   height={},framerate={}/1, \
                   format=I420'.format(width, height, fps)
    caps = Gst.Caps.from_string(text_filter)

    filter.set_property('caps',caps)
    pipeline.add(filter)

    tee = Gst.ElementFactory.make('tee')
    pipeline.add(tee)

    queue1 = Gst.ElementFactory.make('queue')
    pipeline.add(queue1)

    videoscale = Gst.ElementFactory.make('videoscale')
    pipeline.add(videoscale)

    autovideosink = Gst.ElementFactory.make('autovideosink')
    pipeline.add(autovideosink)

    x264 = Gst.ElementFactory.make('x264enc', 'x264')
    x264.set_property('speed-preset','ultrafast')
    x264.set_property('tune','zerolatency')
    x264.set_property('bitrate',bitrate_video)
    x264.set_property('key-int-max',25)
    pipeline.add(x264)
    h264pay = Gst.ElementFactory.make('rtph264pay')
    h264pay.set_property('pt',96)
    h264pay.set_property('config-interval',1)
    pipeline.add(h264pay)
    queue = Gst.ElementFactory.make('rtprtxqueue')
    pipeline.add(queue)
    rtp = Gst.ElementFactory.make('udpsink')
    rtp.set_property('host',ip_destino)
    rtp.set_property('port',int(puerto_rtp))
    pipeline.add(rtp)
    rtcp = Gst.ElementFactory.make('udpsink')
    rtcp.set_property('host',ip_destino)
    rtcp.set_property('port',int(puerto_rtcp))
    rtcp.set_property('sync','false')
    rtcp.set_property('async','false')
    pipeline.add(rtcp)
    drop = Gst.ElementFactory.make('identity', 'drop_video')
    drop.set_property('drop-probability', drop_prob)
    pipeline.add(drop)
    l1 = video.link(convert)
    l2 = convert.link(rate)
    l3 = rate.link(filter)
    l4 = filter.link(tee)
    l5 = tee.link(queue1)
    l6 = queue1.link(videoscale)
    l7 = videoscale.link(autovideosink)
    l8 = tee.link(x264)
    l9 = x264.link(h264pay)
    l10 = h264pay.link(queue)
    l11 = queue.link_pads('src',rtpbin,'send_rtp_sink_0')
    l12 = rtpbin.link_pads('send_rtp_src_0',drop)
    l13 = drop.link(rtp)
    l14 = rtpbin.link_pads('send_rtcp_src_0',rtcp,'sink')
    return l1 and l2 and l3 and l4 and l5 and l6 and l7 and l8 and l9 and l10 and l11 and l12 and l13 and l14

def aac_send(pipeline,rtpbin,puerto_rtp,puerto_rtcp,ip_destino,bitrate_audio,muestras,drop_prob):
    audio = Gst.ElementFactory.make('autoaudiosrc')
    pipeline.add(audio)
    filter = Gst.ElementFactory.make('capsfilter', 'filter_audio')
    text_filter = 'audio/x-raw,format=F32LE,channels=2, \
                   rate={}'.format(muestras)
    caps = Gst.Caps.from_string(text_filter)
    filter.set_property('caps',caps)
    pipeline.add(filter)
    convert = Gst.ElementFactory.make('audioconvert')
    pipeline.add(convert)
    aac = Gst.ElementFactory.make('avenc_aac', 'aac')
    aac.set_property('bitrate',int(bitrate_audio))
    pipeline.add(aac)
    mp4apay = Gst.ElementFactory.make('rtpmp4apay')
    mp4apay.set_property('pt',97)
    pipeline.add(mp4apay)
    queue = Gst.ElementFactory.make('queue')
    pipeline.add(queue)
    rtp = Gst.ElementFactory.make('udpsink')
    rtp.set_property('host',ip_destino)
    rtp.set_property('port',int(puerto_rtp))
    pipeline.add(rtp)
    rtcp = Gst.ElementFactory.make('udpsink')
    rtcp.set_property('host',ip_destino)
    rtcp.set_property('port',int(puerto_rtcp))
    rtcp.set_property('sync','false')
    rtcp.set_property('async','false')
    pipeline.add(rtcp)
    drop = Gst.ElementFactory.make('identity', 'drop_audio')
    drop.set_property('drop-probability', drop_prob)
    pipeline.add(drop)
    l1 = audio.link(filter)
    l2 = filter.link(convert)
    l3 = convert.link(aac)
    l4 = aac.link(mp4apay)
    l5 = mp4apay.link(queue)
    l6 = queue.link_pads('src',rtpbin,'send_rtp_sink_1')
    l7 = rtpbin.link_pads('send_rtp_src_1',drop)
    l8 = drop.link(rtp)
    l9 = rtpbin.link_pads('send_rtcp_src_1',rtcp,'sink')
    return l1 and l2 and l3 and l4 and l5 and l6 and l7 and l8 and l9

def rtcp_recv(pipeline,rtpbin,port_rtcp_1,port_rtcp_2):
    src1 = Gst.ElementFactory.make('udpsrc')
    src1.set_property('port',int(port_rtcp_1))
    pipeline.add(src1)
    src2 = Gst.ElementFactory.make('udpsrc')
    src2.set_property('port',int(port_rtcp_2))
    pipeline.add(src2)
    l1 = src1.link_pads('src',rtpbin,'recv_rtcp_sink_0')
    l2 = src2.link_pads('src',rtpbin,'recv_rtcp_sink_1')
    return l1 and l2

class Videoconferencia(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Variable de control (llamada iniciada o no)

        self.llamada_en_curso = False

        # ID del frame de video local y del video remoto
        self.id_frame_local = self.ui.frame_video_local.winId()
        self.id_frame_remoto = self.ui.frame_video_remoto.winId()

        # Listeners para cada elemento del menu
        self.ui.dial_bitrate_video.valueChanged.connect(self.modificar_br_video)
        self.ui.caja_bitrate_audio.currentTextChanged.connect(self.modificar_br_audio)
        self.ui.caja_fps.currentTextChanged.connect(self.avisar_fps)
        self.ui.caja_resolucion.currentTextChanged.connect(self.avisar_resolucion)
        self.ui.caja_muestras.currentTextChanged.connect(self.avisar_muestras)
        self.ui.dial_volumen.valueChanged.connect(self.modificar_volumen)
        self.ui.check_mute.stateChanged.connect(self.mute_unmute_audio)
        self.ui.boton_iniciar.clicked.connect(self.iniciar_llamada)
        self.ui.boton_finalizar.clicked.connect(self.finalizar_llamada)
        self.ui.slider_drop_video.sliderMoved.connect(self.cambiar_drop_video)
        self.ui.slider_drop_audio.sliderMoved.connect(self.cambiar_drop_audio)


    def iniciar_llamada(self):
        if not self.llamada_en_curso:
            # Creamos los pipelines de emision y recepcion
            Gst.init(None)

            self.pipeline_emision = Gst.Pipeline.new("pipeline")
            self.pipeline_recepcion = Gst.Pipeline.new("pipeline")

            self.rtpbin1 = Gst.ElementFactory.make('rtpbin')
            self.rtpbin2 = Gst.ElementFactory.make('rtpbin')

            self.rtpbin1.set_property('rtp-profile', 'avpf')
            self.rtpbin2.set_property('rtp-profile', 'avpf')
            self.rtpbin2.set_property('do-retransmission', 'true')
            self.rtpbin2.set_property('latency', 500)

            self.pipeline_emision.add(self.rtpbin1)

            self.par_video_destino = self.ui.puerto_dest_recep_video.text()
            self.par_audio_destino = self.ui.puerto_dest_recep_audio.text()
            self.par_video_local = self.ui.puerto_local_recep_video.text()
            self.par_audio_local = self.ui.puerto_local_recep_audio.text()
            self.ip_destino = self.ui.ip_destino.text()

            self.resolucion = self.ui.caja_resolucion.currentText()
            self.fps = self.ui.caja_fps.currentText()
            self.bitrate_video = self.ui.dial_bitrate_video.value() * 1000
            self.bitrate_audio = self.ui.caja_bitrate_audio.currentText()
            self.muestras_audio = self.ui.caja_muestras.currentText()
            self.volumen = self.ui.dial_volumen.value() / 10
            self.drop_prob_video = self.ui.slider_drop_video.value() / 100
            self.drop_prob_audio = self.ui.slider_drop_audio.value() / 100

            if not self.par_video_destino or not self.par_audio_destino or not self.par_video_local or not self.par_audio_local or not self.ip_destino:
                buttonReply = QMessageBox.warning(self, 'Error al iniciar la llamada', 'La información de conexión está incompleta', QMessageBox.Ok)
            else:
                self.rtpbin2.connect('pad-added', on_pad_added, self.pipeline_recepcion, str(int(self.par_video_local)+5), str(int(self.par_audio_local)+5),self.ip_destino)
                self.pipeline_recepcion.add(self.rtpbin2)

                e1 = x264_send(self.pipeline_emision,self.rtpbin1,self.par_video_destino,str(int(self.par_video_destino)+1),self.ip_destino,self.resolucion,self.fps,self.bitrate_video,self.drop_prob_video)
                e2 = aac_send(self.pipeline_emision,self.rtpbin1,self.par_audio_destino,str(int(self.par_audio_destino)+1),self.ip_destino,self.bitrate_audio,self.muestras_audio,self.drop_prob_audio)
                e3 = rtcp_recv(self.pipeline_emision,self.rtpbin1,str(int(self.par_video_destino)+5),str(int(self.par_audio_destino)+5))

                r1 = h264_recv(self.pipeline_recepcion,self.rtpbin2,self.par_video_local)
                r2 = aac_recv(self.pipeline_recepcion,self.rtpbin2,self.par_audio_local,self.volumen)
                r3 = rtcp_recv(self.pipeline_recepcion,self.rtpbin2,str(int(self.par_video_local)+1),str(int(self.par_audio_local)+1))

                # Eventos del pipeline de emision
                self.bus_emision = self.pipeline_emision.get_bus()
                self.bus_emision.add_signal_watch()
                self.bus_emision.enable_sync_message_emission()
                self.bus_emision.connect('sync-message::element', self.on_sync_message_emision)

                self.bus_recepcion = self.pipeline_recepcion.get_bus()
                self.bus_recepcion.add_signal_watch()
                self.bus_recepcion.enable_sync_message_emission()
                self.bus_recepcion.connect('sync-message::element', self.on_sync_message_recepcion)

                # Arrancamos los pipelines
                self.pipeline_emision.set_state(Gst.State.PLAYING)
                self.pipeline_recepcion.set_state(Gst.State.PLAYING)

                self.llamada_en_curso = True

    def finalizar_llamada(self):
        if self.llamada_en_curso:
            self.pipeline_emision.set_state(Gst.State.NULL)
            self.pipeline_recepcion.set_state(Gst.State.NULL)

            self.llamada_en_curso = False
        else:
            QMessageBox.warning(self, 'Error al finalizar la llamada', 'La llamada no está en curso', QMessageBox.Ok)

    def modificar_br_video(self, valor):
        self.ui.label_br_video.setText(str(valor))

        if self.llamada_en_curso:
            self.pipeline_emision.get_by_name('x264').set_property('bitrate', valor*1000)

    def modificar_br_audio(self, valor):
        if self.llamada_en_curso:
            self.pipeline_emision.get_by_name('aac').set_property('bitrate', int(valor))

    def modificar_volumen(self, valor):
        if self.llamada_en_curso:
            if self.ui.check_mute.isChecked() and valor/10 != 0:
                self.ui.check_mute.setChecked(0)
            self.pipeline_recepcion.get_by_name('volumen').set_property('volume', valor/10)

    def mute_unmute_audio(self, checked):
        if self.llamada_en_curso:
            if checked:
                self.modificar_volumen(0)
            else:
                volumen_anterior = self.ui.dial_volumen.value()
                self.modificar_volumen(volumen_anterior)

    def cambiar_drop_video(self, valor):
        self.ui.label_drop_video.setText(str(valor))
        if self.llamada_en_curso:
            self.pipeline_emision.get_by_name('drop_video').set_property('drop-probability', valor/100)

    def cambiar_drop_audio(self, valor):
        self.ui.label_drop_audio.setText(str(valor))
        if self.llamada_en_curso:
            self.pipeline_emision.get_by_name('drop_audio').set_property('drop-probability', valor/100)

    def avisar_fps(self):
        new_fps = self.ui.caja_fps.currentText()
        if self.llamada_en_curso and new_fps != self.fps:
            # Reestablecemos el valor del parámetro
            self.ui.caja_fps.setCurrentText(self.fps)
            QMessageBox.warning(self, 'Error al cambiar el parámetro', 'No puedes cambiar este parámetro con la llamada en curso', QMessageBox.Ok)

    def avisar_resolucion(self):
        new_res = self.ui.caja_resolucion.currentText()
        if self.llamada_en_curso and new_res != self.resolucion:
            # Reestablecemos el valor del parámetro
            self.ui.caja_resolucion.setCurrentText(self.resolucion)
            QMessageBox.warning(self, 'Error al cambiar el parámetro', 'No puedes cambiar este parámetro con la llamada en curso', QMessageBox.Ok)

    def avisar_muestras(self):
        new_muestras = self.ui.caja_muestras.currentText()
        if self.llamada_en_curso and new_muestras != self.muestras_audio:
            # Reestablecemos el valor del parámetro
            self.ui.caja_muestras.setCurrentText(self.muestras_audio)
            QMessageBox.warning(self, 'Error al cambiar el parámetro', 'No puedes cambiar este parámetro con la llamada en curso', QMessageBox.Ok)

    def on_sync_message_emision(self, bus_emision, message):
        if not message.get_structure():
            return True
        message_name = message.get_structure().get_name()
        if message_name == 'prepare-window-handle':
            videosink = message.src
            videosink.set_window_handle(self.id_frame_local)
        return True

    def on_sync_message_recepcion(self, bus_recepcion, message):
        if not message.get_structure():
            return True
        message_name = message.get_structure().get_name()
        if message_name == 'prepare-window-handle':
            videosink = message.src
            videosink.set_window_handle(self.id_frame_remoto)
        return True

if __name__ == "__main__":
    app = QApplication([])
    window = Videoconferencia()
    window.show()
    sys.exit(app.exec_())
