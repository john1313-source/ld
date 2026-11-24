"""브라우저 뷰어용 GLB 내보내기.

실행: python export_web.py   (bpy 모듈 필요, build_model.py가 저장한 .blend를 읽는다)
- 라이트·카메라·라벨은 제외 (뷰어가 자체 조명·시점 사용)
- 절차적 텍스처(줄눈 타일 등)는 glTF로 옮겨지지 않으므로 재질 대표색으로 대체
- 천장·천장설비는 이름('천장', '매입등_', '시스템에어컨_', '라인조명')으로 뷰어에서 켜고 끈다
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(HERE, "brownstone_hwigyeong_114_redesign.blend")
OUT = os.path.join(HERE, "web", "brownstone_114.glb")

EXCLUDE = ("06_라이트", "07_카메라", "08_라벨(평면도용)")


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    for name in EXCLUDE:
        c = bpy.data.collections.get(name)
        if c:
            for o in list(c.all_objects):
                bpy.data.objects.remove(o, do_unlink=True)
    for o in list(bpy.data.objects):
        if o.type in ("LIGHT", "CAMERA", "FONT"):
            bpy.data.objects.remove(o, do_unlink=True)

    # 절차적 노드로 연결된 Base Color / Normal 을 끊고 대표색으로 고정
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        nt = m.node_tree
        b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)   # 한국어 UI는 노드 이름을 번역
        if b is None:
            continue
        for sock in ("Base Color", "Normal"):
            inp = b.inputs.get(sock)
            if inp is not None:
                for link in list(inp.links):
                    nt.links.remove(link)
        b.inputs["Base Color"].default_value = m.diffuse_color

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUT,
        export_format="GLB",
        export_apply=True,          # 베벨 모디파이어 적용
        export_yup=True,
        export_lights=False,
        export_cameras=False,
        export_materials="EXPORT",
        export_draco_mesh_compression_enable=False,
    )
    print("exported", OUT, os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    main()
    sys.exit(0)
