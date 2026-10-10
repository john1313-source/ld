"""블렌더에서 한 번만 실행: RTX 4080 SUPER(OptiX)로 렌더하도록 환경설정을 바꾼다.

사용법
  1) 블렌더에서 brownstone_hwigyeong_114_redesign.blend 를 연다
  2) 위쪽 탭 'Scripting' → 가운데 편집기에서 Open → 이 파일(setup_gpu.py) → ▶ Run Script
  3) 아래 'Info'/콘솔에 'GPU 설정 완료'와 장치 이름이 나오면 끝. 환경설정은 저장되어 다음부터 다시 할 필요 없음
"""
import bpy

prefs = bpy.context.preferences
cycles_prefs = prefs.addons["cycles"].preferences

chosen = None
for backend in ("OPTIX", "CUDA"):          # RTX 4080 SUPER: OptiX 우선, 안 되면 CUDA
    try:
        cycles_prefs.compute_device_type = backend
    except TypeError:
        continue
    cycles_prefs.get_devices()
    gpus = [d for d in cycles_prefs.devices if d.type == backend]
    if gpus:
        chosen = backend
        break

if chosen is None:
    raise RuntimeError("OptiX/CUDA GPU를 찾지 못했습니다. NVIDIA 드라이버를 최신으로 업데이트한 뒤 다시 실행하세요.")

for d in cycles_prefs.devices:
    d.use = d.type == chosen                  # GPU만 사용 (CPU 혼합은 오히려 느려질 수 있음)

bpy.ops.wm.save_userpref()

sc = bpy.context.scene
sc.cycles.device = "GPU"
sc.cycles.samples = 256
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = "OPTIX"
except TypeError:
    pass

# 3D 뷰를 Material Preview로
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        for sp in area.spaces:
            if sp.type == "VIEW_3D":
                sp.shading.type = "MATERIAL"

names = ", ".join(d.name for d in cycles_prefs.devices if d.use)
msg = f"GPU 설정 완료: {chosen} — {names}"
print(msg)
bpy.context.window_manager.popup_menu(lambda self, ctx: self.layout.label(text=msg), title="setup_gpu", icon="INFO")
