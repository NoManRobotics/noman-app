import os
import time
import numpy as np
import sounddevice as sd
import pyaudio
import requests
import zipfile
import shutil
import tarfile
import sherpa_ncnn
from io import BytesIO

from .config import Config

class SpeechRecognitionManager:
    def __init__(self):
        """初始化语音识别管理器"""
        try:
            self.device = None
            self._last_noise_adjust_time = 0  # 记录上次噪声调整时间
            self._noise_adjust_interval = 30  # 噪声调整间隔（秒）

            self.sherpa = None
            self.recording = False  # 录音状态标志
            self.stream = None  # 录音流

            # 使用Config.base_dir构建模型路径
            self.model_path = os.path.join(Config.base_dir, "models", "sherpa-ncnn-streaming-zipformer-bilingual-zh-en-2023-02-13")
            self.model_available = self.model_exists()
            
            # 初始化sherpa-ncnn识别器
            if self.model_available:
                self.init_sherpa()
            
        except Exception as e:
            print(f"初始化失败: {str(e)}")
            raise

    def init_sherpa(self):
        self.sherpa = sherpa_ncnn.Recognizer(
            tokens=os.path.join(self.model_path, "tokens.txt"),
            encoder_param=os.path.join(self.model_path, "encoder_jit_trace-pnnx.ncnn.param"),
            encoder_bin=os.path.join(self.model_path, "encoder_jit_trace-pnnx.ncnn.bin"),
            decoder_param=os.path.join(self.model_path, "decoder_jit_trace-pnnx.ncnn.param"),
            decoder_bin=os.path.join(self.model_path, "decoder_jit_trace-pnnx.ncnn.bin"),
            joiner_param=os.path.join(self.model_path, "joiner_jit_trace-pnnx.ncnn.param"),
            joiner_bin=os.path.join(self.model_path, "joiner_jit_trace-pnnx.ncnn.bin"),
            num_threads=4
        )
    
        # 设置端点检测参数
        self.sherpa.enable_endpoint_detection = True
        self.sherpa.rule1_min_trailing_silence = 2.0  # 结尾静音检测时间
        self.sherpa.rule2_min_trailing_silence = 0.8  # 短语间静音检测时间
        self.sherpa.rule3_min_utterance_length = 0.5  # 最小语音长度

    def model_exists(self):
        """检查模型文件是否存在
        
        Returns:
            bool: 如果模型文件都存在返回True，否则返回False
        """
        model_dir = os.path.join(Config.base_dir, "models", "sherpa-ncnn-streaming-zipformer-bilingual-zh-en-2023-02-13")
        
        # 检查模型目录是否存在
        if not os.path.exists(model_dir):
            return False
            
        # 检查必要的模型文件是否都存在
        required_files = [
            "tokens.txt",
            "encoder_jit_trace-pnnx.ncnn.param",
            "encoder_jit_trace-pnnx.ncnn.bin",
            "decoder_jit_trace-pnnx.ncnn.param",
            "decoder_jit_trace-pnnx.ncnn.bin",
            "joiner_jit_trace-pnnx.ncnn.param",
            "joiner_jit_trace-pnnx.ncnn.bin"
        ]
        
        for file in required_files:
            if not os.path.exists(os.path.join(model_dir, file)):
                return False
                
        return True
        
    def download_model(self, remote=""):
        """从远程下载模型文件
        
        Args:
            remote (str, optional): 远程模型ZIP文件URL。如果为空，使用默认地址。
        
        Returns:
            bool: 下载成功返回True，否则返回False
        """
        try:
            models_dir = os.path.join(Config.base_dir, "models")
            model_dir = os.path.join(models_dir, "sherpa-ncnn-streaming-zipformer-bilingual-zh-en-2023-02-13")
            
            # 确保models目录存在
            if not os.path.exists(models_dir):
                os.makedirs(models_dir, exist_ok=True)
            
            # 如果未提供远程URL，使用默认URL
            if not remote:
                remote = "https://github.com/k2-fsa/sherpa-ncnn/releases/download/models/sherpa-ncnn-streaming-zipformer-bilingual-zh-en-2023-02-13.tar.bz2"
            
            # 下载模型文件
            response = requests.get(remote, stream=True)
            response.raise_for_status()
            
            # 创建临时目录用于解压
            temp_dir = os.path.join(Config.base_dir, 'temp_model')
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
            
            # 根据文件类型选择解压方法
            if remote.endswith('.zip'):
                # 解压ZIP文件
                with zipfile.ZipFile(BytesIO(response.content)) as zip_ref:
                    zip_ref.extractall(temp_dir)
            elif remote.endswith('.tar.bz2') or remote.endswith('.tar.gz') or remote.endswith('.tgz'):
                # 解压TAR文件
                file_like_object = BytesIO(response.content)
                with tarfile.open(fileobj=file_like_object, mode='r:*') as tar_ref:
                    tar_ref.extractall(temp_dir)
            else:
                print("不支持的文件格式，仅支持zip或tar压缩文件")
                return False
                
            # 移动解压后的文件到目标目录
            if os.path.exists(model_dir):
                shutil.rmtree(model_dir)
                
            # 检查临时目录中的文件结构
            extracted_files = os.listdir(temp_dir)
            if len(extracted_files) == 1 and os.path.isdir(os.path.join(temp_dir, extracted_files[0])):
                # 如果解压出来的是一个子目录，移动子目录的内容
                source_dir = os.path.join(temp_dir, extracted_files[0])
                os.makedirs(model_dir, exist_ok=True)
                for item in os.listdir(source_dir):
                    s = os.path.join(source_dir, item)
                    d = os.path.join(model_dir, item)
                    shutil.move(s, d)
            else:
                # 直接移动临时目录的内容
                shutil.move(temp_dir, model_dir)
                
            # 清理临时目录
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

            self.model_available = self.model_exists()
            self.init_sherpa()
                
            return True
            
        except Exception as e:
            print(f"模型下载失败: {str(e)}")
            return False

    def list_audio_devices(self):
        """列出所有音频输入设备"""
        try:
            p = pyaudio.PyAudio()
            devices = [(i, p.get_device_info_by_index(i)) 
                      for i in range(p.get_device_count()) 
                      if p.get_device_info_by_index(i)['maxInputChannels'] > 0]
            p.terminate()
            return devices
        except Exception as e:
            print(f"获取音频设备失败: {str(e)}")
            return []

    def _process_audio(self, audio):
        """处理音频数据为sherpa-ncnn可接受的格式"""
        try:
            raw_data = audio.get_raw_data()
            np_data = np.frombuffer(raw_data, dtype=np.int16)
            float_data = np_data.astype(np.float32) / 32768.0
            return float_data
        except Exception as e:
            print(f"音频处理失败: {str(e)}")
            raise

    def _should_adjust_noise(self):
        """判断是否需要调整环境噪声"""
        current_time = time.time()
        if current_time - self._last_noise_adjust_time > self._noise_adjust_interval:
            self._last_noise_adjust_time = current_time
            return True
        return False

    def start_recording(self, callback_status=None):
        """开始录音并实时识别"""

        if not self.model_available:
            return "语音模型未安装，请先安装语音模型"

        try:
            if callback_status:
                callback_status("正在聆听...")
            
            sample_rate = 16000
            samples_per_read = int(0.05 * sample_rate)  # 每次读取50ms的音频，提高响应性
            last_result = ""
            final_result = ""  # 存储最终识别结果
            
            # 设置录音状态
            self.recording = True
            
            # 重置识别器状态
            self.sherpa.reset()
            
            # 创建录音流
            self.stream = sd.InputStream(
                channels=1, 
                dtype="float32", 
                samplerate=sample_rate,
                device=self.device
            )
            
            with self.stream:
                while self.recording:
                    try:
                        # 使用阻塞式读取，但通过较小的缓冲区大小确保响应性
                        samples, overflowed = self.stream.read(samples_per_read)
                        
                        if not self.recording:  # 检查是否已停止录音
                            break
                            
                        if overflowed:
                            print("音频缓冲区溢出")
                            continue
                            
                        samples = samples.reshape(-1)
                        
                        # 实时送入识别器
                        self.sherpa.accept_waveform(sample_rate, samples)
                        
                        # 获取识别结果
                        result = self.sherpa.text
                        is_endpoint = self.sherpa.is_endpoint
                        
                        # 有新的识别结果时回调
                        if result and (last_result != result):
                            last_result = result
                            final_result = result  # 保存最新的识别结果
                            if callback_status:
                                callback_status(f"正在识别: {result}")
                        
                        # 检测到语音结束
                        if is_endpoint:
                            if result:
                                if callback_status:
                                    callback_status(f"识别结果: {result}")
                                final_result = result  # 确保保存最终结果
                                self.recording = False  # 停止录音
                                return result
                            self.sherpa.reset()
                            
                        # 检查音量
                        if len(samples) > 0 and np.max(np.abs(samples)) < 0.01:  # 音量过小检测
                            continue
                            
                    except Exception as e:
                        if self.recording:  # 只有在还在录音时才打印错误
                            print(f"读取音频数据时出错: {str(e)}")
                        break
                    
            # 清理录音流
            self.stream = None
            self.recording = False
            
            if callback_status:
                callback_status("录音已停止")
            
            # 如果有识别结果，即使是用户主动停止也返回结果
            if final_result and final_result.strip():
                print(f"返回最终识别结果: {final_result}")
                return final_result
            
            return ""  # 返回空字符串表示没有识别到内容
                    
        except Exception as e:
            error_msg = f"语音识别错误: {str(e)}"
            print(error_msg)
            self.recording = False
            self.stream = None
            if callback_status:
                callback_status(f"错误: {str(e)}")
            
            # 即使出错，如果有识别结果也返回
            if 'final_result' in locals() and final_result and final_result.strip():
                print(f"出错但返回已识别结果: {final_result}")
                return final_result
                
            return ""  # 出错且无识别结果时返回空字符串

    def stop_recording(self):
        """停止录音并重置"""
        try:
            print("正在停止录音...")
            self.recording = False
            
            # 短暂延迟确保循环检测到状态变化
            time.sleep(0.2)
            
            # 如果录音流存在，强制关闭它
            if self.stream is not None:
                try:
                    # 强制停止流
                    if hasattr(self.stream, 'stop'):
                        self.stream.stop()
                    if hasattr(self.stream, 'close'):
                        self.stream.close()
                except Exception as e:
                    print(f"关闭录音流时出错: {str(e)}")
                finally:
                    self.stream = None
            
            # 重置识别器
            if self.sherpa is not None:
                self.sherpa.reset()
                
        except Exception as e:
            print(f"停止录音失败: {str(e)}")

    def set_device(self, device_id):
        """设置录音设备"""
        try:
            self.device = device_id
        except Exception as e:
            print(f"设置设备失败: {str(e)}")