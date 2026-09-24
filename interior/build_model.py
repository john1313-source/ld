"""
브라운스톤휘경 전용 114.58㎡(공급 140.46㎡, 42.49평/34.66평) — 발코니 전체 확장 재설계 3D 모델

실행 방법
  1) 블렌더 GUI:  Scripting 탭 → 이 파일 열기 → Run Script   (모델만 생성)
  2) 명령줄:      blender -b -P build_model.py -- --render      (모델 생성 + 저장 + 렌더)
  3) bpy 모듈:    python build_model.py --render [--quick]

옵션
  --render   카메라 전체 렌더 (renders/*.png)
  --quick    저해상도·저샘플 테스트 렌더
  --save     .blend 저장 (--render 시 자동)

치수 근거 (README.md 참고)
  - 도면 이미지(오늘의집, 465×463px)의 벽 중심선을 픽셀 단위로 측정
  - 축척 기준: 사용자 제공 실측값 — 북측 침실(서재) 2950 × 3100 mm
      가로 85px → 2950mm (34.71 mm/px), 세로 88px → 3100mm (35.23 mm/px)
  - 검증: 같은 축척으로 계산한 전용 외곽 면적 113.9㎡ vs 공고 114.58㎡ (차이 0.6%)
  - 실측값 외 모든 치수는 '추정치'. 현장 실측 후 SX, SY 및 PX_* 좌표만 고치면 전체가 갱신됨
"""

import math
import os
import sys

import bpy  # noqa: E402  (bpy 모듈 환경에서는 bmesh보다 먼저 import)
import bmesh
from mathutils import Matrix, Vector

# ────────────────────────────────────────────────────────────────────────────
# 1. 치수 설정 (추정치 — 실측 후 교체)
# ────────────────────────────────────────────────────────────────────────────
SX = 2.950 / 85.0   # m/px, 가로(동-서)  ← 실측 기준 침실 가로 2950mm
SY = 3.100 / 88.0   # m/px, 세로(남-북)  ← 실측 기준 침실 세로 3100mm
PX_X0 = 18.5        # 도면상 서측 외벽 중심선 x(px)
PX_Y0 = 301.5       # 도면상 기존 남측 창호벽(확장 전 거실 창) 중심선 y(px)

H = 2.30            # 천장고 (가정 — 2013년 입주 단지 일반값, 실측 필요)
T_EXT = 0.20        # 외벽 두께 (가정)
T_INT = 0.12        # 칸막이벽 두께 (가정)
ENTRY_DROP = 0.10   # 현관 단차 (가정)

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
BLEND_PATH = os.path.join(HERE, "brownstone_hwigyeong_114_redesign.blend")
RENDER_DIR = os.path.join(HERE, "renders")
KO_FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def X(px):
    return (px - PX_X0) * SX


def Y(py):
    return (PX_Y0 - py) * SY


# ────────────────────────────────────────────────────────────────────────────
# 2. 공통 유틸
# ────────────────────────────────────────────────────────────────────────────
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def set_input(node, name, value):
    """블렌더 4.x/5.x 입력 이름 차이를 흡수 (비활성 입력도 탐색)."""
    for inp in node.inputs:
        if inp.name == name:
            inp.default_value = value
            return True
    return False


MATS = {}


def mat(name, color, rough=0.5, metal=0.0, transmission=0.0, emission=None,
        emission_strength=0.0, alpha=1.0, coat=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    set_input(b, "Base Color", (*color, 1.0))
    set_input(b, "Roughness", rough)
    set_input(b, "Metallic", metal)
    set_input(b, "Transmission Weight", transmission)
    set_input(b, "Coat Weight", coat)
    if transmission > 0:
        set_input(b, "IOR", 1.45)
    if emission is not None:
        set_input(b, "Emission Color", (*emission, 1.0))
        set_input(b, "Emission Strength", emission_strength)
    if alpha < 1.0:
        set_input(b, "Alpha", alpha)
    m.diffuse_color = (*color, 1.0)
    MATS[name] = m
    return m


def tile_mat(name, c1, c2, grout, w, h, rough=0.4, offset=0.0, grout_size=0.0025,
             vertical=False, bump=0.15):
    """월드 좌표 기반 줄눈 타일/마루. vertical=True 이면 벽면용 (x+y, z) 매핑."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    set_input(b, "Roughness", rough)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    if vertical:
        add = nt.nodes.new("ShaderNodeMath")
        add.operation = "ADD"
        nt.links.new(sep.outputs["X"], add.inputs[0])
        nt.links.new(sep.outputs["Y"], add.inputs[1])
        nt.links.new(add.outputs[0], comb.inputs["X"])
        nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
    else:
        nt.links.new(sep.outputs["X"], comb.inputs["X"])
        nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = offset
    br.offset_frequency = 2
    br.squash = 1.0
    br.squash_frequency = 1
    set_input(br, "Color1", (*c1, 1))
    set_input(br, "Color2", (*c2, 1))
    set_input(br, "Mortar", (*grout, 1))
    set_input(br, "Scale", 1.0)
    set_input(br, "Mortar Size", grout_size)
    set_input(br, "Mortar Smooth", 0.1)
    set_input(br, "Bias", 0.0)
    set_input(br, "Brick Width", w)
    set_input(br, "Row Height", h)
    nt.links.new(comb.outputs[0], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    set_input(bp, "Strength", bump)
    set_input(bp, "Distance", 0.002)
    nt.links.new(br.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = (*c1, 1.0)
    MATS[name] = m
    return m


def _link(obj, collection):
    collection.objects.link(obj)
    return obj


def _mesh_obj(name, bm, material, collection, bevel=0.0, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    if material is not None:
        me.materials.append(material)
    if bevel > 0:
        md = obj.modifiers.new("Bevel", "BEVEL")
        md.width = bevel
        md.segments = 2
        md.limit_method = "ANGLE"
        md.harden_normals = False
    return _link(obj, collection)


def _xf(pivot, angle):
    if not angle:
        return None
    px, py = pivot
    return (Matrix.Translation((px, py, 0)) @ Matrix.Rotation(angle, 4, "Z")
            @ Matrix.Translation((-px, -py, 0)))


def box(name, x1, y1, z1, x2, y2, z2, material, collection, bevel=0.0,
        pivot=None, angle=0.0):
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    z1, z2 = sorted((z1, z2))
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x1 if v.co.x < 0 else x2
        v.co.y = y1 if v.co.y < 0 else y2
        v.co.z = z1 if v.co.z < 0 else z2
    m = _xf(pivot or (x1, y1), angle)
    if m:
        bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    return _mesh_obj(name, bm, material, collection, bevel)


def cyl(name, cx, cy, z1, z2, r, material, collection, seg=32, r2=None, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r, radius2=r if r2 is None else r2, depth=z2 - z1)
    bmesh.ops.translate(bm, vec=Vector((cx, cy, (z1 + z2) / 2)), verts=bm.verts)
    return _mesh_obj(name, bm, material, collection, bevel, smooth=True)


def sphere(name, cx, cy, cz, r, material, collection, sz=1.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=r)
    bmesh.ops.scale(bm, vec=Vector((1, 1, sz)), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector((cx, cy, cz)), verts=bm.verts)
    return _mesh_obj(name, bm, material, collection, smooth=True)


def pxrect(x1, y1, x2, y2):
    """도면 px 사각형 → (xmin, ymin, xmax, ymax) m."""
    xa, xb = sorted((X(x1), X(x2)))
    ya, yb = sorted((Y(y1), Y(y2)))
    return xa, ya, xb, yb


# ────────────────────────────────────────────────────────────────────────────
# 3. 재질 (모던 미니멀 팔레트)
# ────────────────────────────────────────────────────────────────────────────
def build_materials():
    M = {}
    M["paint"] = mat("벽_도장_웜화이트", (0.83, 0.82, 0.79), 0.92)
    M["ceiling"] = mat("천장_화이트", (0.88, 0.88, 0.87), 0.95)
    M["porcelain"] = tile_mat("바닥_포세린_600x1200_웜그레이", (0.66, 0.64, 0.61),
                              (0.64, 0.62, 0.59), (0.5, 0.49, 0.47), 1.2, 0.6, rough=0.28)
    M["oak"] = tile_mat("바닥_광폭강마루_라이트오크", (0.60, 0.47, 0.34), (0.55, 0.42, 0.30),
                        (0.30, 0.22, 0.16), 1.2, 0.19, rough=0.45, offset=0.5,
                        grout_size=0.0012, bump=0.05)
    M["bath_floor"] = tile_mat("욕실_바닥_300x600_차콜", (0.25, 0.25, 0.25), (0.23, 0.23, 0.23),
                               (0.35, 0.35, 0.35), 0.6, 0.3, rough=0.5)
    M["bath_wall"] = tile_mat("욕실_벽_600x1200_라이트그레이", (0.72, 0.71, 0.69),
                              (0.70, 0.69, 0.67), (0.6, 0.6, 0.58), 0.6, 1.2, rough=0.2,
                              vertical=True)
    M["entry_floor"] = tile_mat("현관_바닥_600x600_다크그레이", (0.16, 0.16, 0.16),
                                (0.15, 0.15, 0.15), (0.3, 0.3, 0.3), 0.6, 0.6, rough=0.45)
    M["utility"] = mat("다용도_바닥_시멘트", (0.45, 0.45, 0.44), 0.8)
    M["slab"] = tile_mat("아트월_포세린슬랩_라이트스톤", (0.80, 0.79, 0.76), (0.79, 0.78, 0.75),
                         (0.70, 0.70, 0.68), 1.2, 2.4, rough=0.25, vertical=True, bump=0.05)
    M["cab_white"] = mat("가구_무광화이트", (0.86, 0.86, 0.84), 0.45)
    M["cab_greige"] = mat("가구_그레이지", (0.62, 0.59, 0.55), 0.5)
    M["cab_oak"] = mat("가구_오크무늬", (0.55, 0.41, 0.28), 0.5)
    M["counter"] = mat("상판_세라믹_화이트", (0.90, 0.90, 0.88), 0.18)
    M["black"] = mat("금속_무광블랙", (0.02, 0.02, 0.02), 0.4, metal=0.7)
    M["chrome"] = mat("금속_크롬", (0.8, 0.8, 0.8), 0.12, metal=1.0)
    M["steel"] = mat("금속_스테인리스", (0.6, 0.6, 0.6), 0.3, metal=1.0)
    M["glass"] = mat("유리_투명", (0.95, 0.97, 0.97), 0.0, transmission=1.0)
    M["frosted"] = mat("유리_반투명", (0.9, 0.9, 0.9), 0.35, transmission=0.9)
    M["mirror"] = mat("거울", (0.95, 0.95, 0.95), 0.02, metal=1.0)
    M["frame"] = mat("창호_프레임_다크그레이", (0.10, 0.10, 0.10), 0.5, metal=0.3)
    M["fabric_sofa"] = mat("패브릭_부클레_아이보리", (0.72, 0.69, 0.63), 1.0)
    M["fabric_gray"] = mat("패브릭_웜그레이", (0.42, 0.40, 0.37), 1.0)
    M["bedding"] = mat("침구_화이트", (0.88, 0.87, 0.84), 0.95)
    M["bedding_accent"] = mat("침구_세이지", (0.46, 0.51, 0.43), 0.95)
    M["leather"] = mat("가죽_코냑", (0.36, 0.20, 0.11), 0.55)
    M["rug"] = mat("러그_베이지", (0.62, 0.57, 0.49), 1.0)
    M["tv"] = mat("TV_블랙글라스", (0.01, 0.01, 0.01), 0.05, coat=1.0)
    M["porcelain_ware"] = mat("위생도기_화이트", (0.93, 0.93, 0.92), 0.1, coat=0.5)
    M["plant"] = mat("식물_잎", (0.10, 0.22, 0.08), 0.7)
    M["pot"] = mat("화분_테라코타", (0.45, 0.27, 0.18), 0.8)
    M["curtain"] = mat("커튼_쉬어린넨", (0.90, 0.88, 0.84), 1.0, transmission=0.4)
    M["book"] = mat("책_혼합", (0.35, 0.30, 0.26), 0.8)
    M["led"] = mat("LED_라인조명", (1.0, 0.9, 0.78), 0.5, emission=(1.0, 0.86, 0.70),
                   emission_strength=12.0)
    M["downlight"] = mat("매입등", (1.0, 1.0, 1.0), 0.5, emission=(1.0, 0.9, 0.78),
                         emission_strength=25.0)
    M["label"] = mat("라벨", (0.0, 0.0, 0.0), 1.0)
    M["label_sub"] = mat("라벨_보조", (0.25, 0.08, 0.02), 1.0)
    M["outdoor_unit"] = mat("실외기실_바닥", (0.55, 0.55, 0.55), 0.9)
    M["louver"] = mat("루버도어", (0.75, 0.75, 0.74), 0.6)
    return M


# ────────────────────────────────────────────────────────────────────────────
# 4. 건축 (벽·개구부·바닥·천장)
# ────────────────────────────────────────────────────────────────────────────
WALL_IDS = []
DOORS = []      # 문짝 생성용 기록
WINDOWS = []    # 창호 생성용 기록


def wall(name, p1, p2, t, M, C, openings=(), material=None):
    """
    도면 px 중심선 (p1→p2, 수평 또는 수직) 벽 생성.
    openings: dict(c=중심 px, w=폭 m, sill=하단 m, head=상단 m, kind='door'|'window'|'open', ...)
    """
    material = material or M["paint"]
    (ax, ay), (bx, by) = p1, p2
    horiz = abs(ay - by) < 1e-6
    if horiz:
        a, b = sorted((X(ax), X(bx)))
        fixed = Y(ay)
    else:
        a, b = sorted((Y(ay), Y(by)))
        fixed = X(ax)
    # 교차부 면 겹침(동일 평면 → 렌더 검은 줄) 방지: 끝을 2mm 덜 연장
    a -= t / 2 - 0.002
    b += t / 2 - 0.002
    z0 = -ENTRY_DROP - 0.02

    ops = []
    for o in openings:
        c = X(o["c"]) if horiz else Y(o["c"])
        ops.append((c - o["w"] / 2, c + o["w"] / 2, o))
    ops.sort(key=lambda s: s[0])

    top = H - 0.0004 * (len(WALL_IDS) % 7)   # 겹치는 벽 윗면 z-fighting 방지용 미세 오프셋
    WALL_IDS.append(name)

    def piece(tag, s, e, zb, zt):
        if e - s < 1e-4 or zt - zb < 1e-4:
            return
        zt = top if zt >= H - 1e-6 else zt
        if horiz:
            box(f"{name}_{tag}", s, fixed - t / 2, zb, e, fixed + t / 2, zt, material, C)
        else:
            box(f"{name}_{tag}", fixed - t / 2, s, zb, fixed + t / 2, e, zt, material, C)

    cur = a
    for i, (s, e, o) in enumerate(ops):
        piece(f"solid{i}", cur, s, z0, H)
        piece(f"sill{i}", s, e, z0, o.get("sill", 0.0) if o.get("sill", 0.0) > 0 else z0)
        piece(f"head{i}", s, e, o.get("head", 2.1), H)
        rec = dict(o, horiz=horiz, s=s, e=e, fixed=fixed, t=t, wall=name)
        (WINDOWS if o["kind"] == "window" else DOORS).append(rec)
        cur = e
    piece("solid_end", cur, b, z0, H)


def D(c, w=0.9, head=2.1, swing=1, hinge="s", kind="door", leaf=True, style="flush"):
    return dict(c=c, w=w, sill=0.0, head=head, swing=swing, hinge=hinge, kind=kind,
                leaf=leaf, style=style)


def W(c, w, sill=0.45, head=2.15, split=2):
    return dict(c=c, w=w, sill=sill, head=head, kind="window", split=split)


def build_architecture(M):
    C = coll("01_벽체")
    # ── 외벽 (확장 후 새 외곽선) ─────────────────────────────────────────
    ext = [
        ("외벽_서측", (18.5, 24.5), (18.5, 343.5), []),
        ("외벽_북측_서재", (18.5, 24.5), (145, 24.5), [W(96, 2.4, sill=0.9, head=2.1)]),
        ("외벽_북측_실외기1", (145, 5.5), (145, 24.5), []),
        ("외벽_북측_주방", (145, 5.5), (325, 5.5),
         [W(208, 2.5, sill=1.0, head=2.1), W(283.5, 0.9, sill=1.0, head=2.1, split=1)]),
        ("외벽_동측_상부", (325, 5.5), (325, 89), []),
        ("외벽_현관", (325, 89), (387, 89), [D(365, 1.0, head=2.1, swing=1, hinge="e",
                                               style="entry")]),
        ("외벽_현관동측", (387, 89), (387, 167.5), []),
        ("외벽_팬트리북측", (387, 167.5), (424.5, 167.5), []),
        ("외벽_동측", (424.5, 167.5), (424.5, 332.5), []),
        ("외벽_남측_자녀방", (263.5, 332.5), (424.5, 332.5),
         [W(303.5, 2.2), W(384, 2.2)]),
        ("외벽_남측_단차", (263.5, 332.5), (263.5, 343.5), []),
        ("외벽_남측_거실안방", (18.5, 343.5), (263.5, 343.5),
         [W(79, 3.5), W(201.5, 3.9, sill=0.3, head=2.2, split=3)]),
    ]
    for n, a, b, o in ext:
        wall(n, a, b, T_EXT, M, C, o)

    # ── 비확장 유지 공간 (실외기실/대피공간 추정) 경계벽 ─────────────────
    keep = [
        ("유지_실외기A_동", (48, 24.5), (48, 53.5), [D(38.8, 0.55, head=1.9, swing=-1, style="louver")]),
        ("유지_실외기B_남", (145, 24.5), (162.5, 24.5), []),
        ("유지_실외기B_동", (162.5, 5.5), (162.5, 24.5), [D(15, 0.5, head=1.9, swing=-1, style="louver")]),
        ("유지_실외기C_서", (305, 5.5), (305, 53.5),
         [D(17.5, 0.55, head=1.9, swing=-1, style="louver"),
          D(41.5, 0.55, head=1.9, swing=-1, style="louver")]),
        ("유지_실외기C_칸막이", (305, 29.5), (325, 29.5), []),
        ("유지_대피공간_북", (262, 53.5), (325, 53.5), [D(286, 0.55, head=1.9, swing=1, style="louver")]),
        ("유지_대피공간_칸막이", (296, 53.5), (296, 76.5), []),
        ("유지_대피공간_남", (276.5, 76.5), (325, 76.5), []),
    ]
    for n, a, b, o in keep:
        wall(n, a, b, 0.15, M, C, o)

    # ── 내부 칸막이 (방 개수 유지) ───────────────────────────────────────
    inner = [
        ("벽_안방욕실북", (18.5, 53.5), (77.5, 53.5), []),
        ("벽_안방욕실_서재", (77.5, 53.5), (77.5, 141.5), []),
        ("벽_서재확장_주방확장", (162.5, 24.5), (162.5, 53.5), []),
        ("벽_서재확장북", (77.5, 53.5), (77.5, 53.5), []),
        ("벽_욕실_드레스", (18.5, 128), (77.5, 128), [D(52, 0.8, swing=1, hinge="e")]),
        ("벽_서재남", (77.5, 141.5), (162.5, 141.5), [D(146, 0.9, swing=1, hinge="e")]),
        ("벽_서재_주방", (162.5, 53.5), (162.5, 141.5), []),
        ("벽_드레스_복도", (86.5, 128), (86.5, 185.5), []),
        ("벽_안방북", (18.5, 185.5), (139.5, 185.5),
         [D(61, 0.9, kind="open", leaf=False), D(124.5, 0.9, swing=-1, hinge="e")]),
        ("벽_안방_거실", (139.5, 185.5), (139.5, 343.5), []),
        ("벽_주방_세탁실", (262, 5.5), (262, 53.5), [D(38, 0.8, swing=1, style="pocket")]),
        ("벽_주방_공용욕실", (276.5, 53.5), (276.5, 145.5), []),
        ("벽_공용욕실남", (276.5, 145.5), (325, 145.5), [D(302, 0.8, swing=1, hinge="e")]),
        ("벽_공용욕실_신발장", (325, 76.5), (325, 145.5), []),
        ("벽_현관_중문", (325, 145.5), (387, 145.5), [D(365.3, 1.45, kind="open", leaf=False)]),
        ("벽_팬트리서측", (387, 167.5), (387, 197.5), [D(182.5, 0.75, swing=-1, hinge="s")]),
        ("벽_자녀방북", (263.5, 197.5), (424.5, 197.5),
         [D(283, 0.9, swing=-1, hinge="s"), D(362, 0.9, swing=-1, hinge="s")]),
        ("벽_거실_자녀방1", (263.5, 197.5), (263.5, 332.5), []),
        ("벽_자녀방1_자녀방2", (343.5, 197.5), (343.5, 332.5), []),
    ]
    for n, a, b, o in inner:
        if a == b:
            continue
        wall(n, a, b, T_INT, M, C, o)


def build_openings(M):
    C = coll("02_창호_문")
    for i, w in enumerate(WINDOWS):
        s, e, f, t, horiz = w["s"], w["e"], w["fixed"], w["t"], w["horiz"]
        zb, zt = w["sill"], w["head"]
        fw = 0.05   # 프레임 폭
        ft = 0.07   # 프레임 깊이

        def fb(tag, a1, a2, z1, z2, mm):
            if horiz:
                box(f"창_{i}_{tag}", a1, f - ft / 2, z1, a2, f + ft / 2, z2, mm, C)
            else:
                box(f"창_{i}_{tag}", f - ft / 2, a1, z1, f + ft / 2, a2, z2, mm, C)

        fb("하", s, e, zb, zb + fw, M["frame"])
        fb("상", s, e, zt - fw, zt, M["frame"])
        fb("좌", s, s + fw, zb, zt, M["frame"])
        fb("우", e - fw, e, zb, zt, M["frame"])
        n = w.get("split", 2)
        for k in range(1, n):
            m = s + (e - s) * k / n
            fb(f"중{k}", m - fw / 2, m + fw / 2, zb, zt, M["frame"])
        g = 0.006
        if horiz:
            gl = box(f"창_{i}_유리", s + fw, f - g, zb + fw, e - fw, f + g, zt - fw, M["glass"], C)
        else:
            gl = box(f"창_{i}_유리", f - g, s + fw, zb + fw, f + g, e - fw, zt - fw, M["glass"], C)
        gl.visible_shadow = False   # 햇빛이 유리를 통과하도록 (Cycles 수렴 속도용)

    for i, d in enumerate(DOORS):
        if not d.get("leaf"):
            continue
        s, e, f, horiz = d["s"], d["e"], d["fixed"], d["horiz"]
        th = 0.04
        style = d.get("style", "flush")
        if style == "pocket":
            # 포켓 슬라이딩: 문짝은 벽 속으로 들어간 상태 → 반쯤 열린 모습으로 표현
            if horiz:
                box(f"문_{i}_슬라이딩", s, f - th / 2, 0, s + (e - s) * 0.3, f + th / 2,
                    d["head"], M["frosted"], C)
            else:
                box(f"문_{i}_슬라이딩", f - th / 2, s, 0, f + th / 2, s + (e - s) * 0.3,
                    d["head"], M["frosted"], C)
            continue
        m_leaf = {"entry": M["frame"], "louver": M["louver"]}.get(style, M["paint"])
        w = e - s
        hinge_at_start = d.get("hinge", "s") in ("s", "w", "n")
        sw = d.get("swing", 1)
        z0 = -ENTRY_DROP if style == "entry" else 0.0
        if horiz:
            hx = s if hinge_at_start else e
            # 문짝을 90° 열린 상태로 배치 (벽에 수직, swing 방향)
            y_a = f
            y_b = f + sw * w
            box(f"문_{i}_문짝", hx - th / 2 if hinge_at_start else hx - th / 2, min(y_a, y_b),
                z0, hx + th / 2, max(y_a, y_b), d["head"] - 0.01, m_leaf, C, bevel=0.003)
        else:
            hy = s if hinge_at_start else e
            x_a = f
            x_b = f + sw * w
            box(f"문_{i}_문짝", min(x_a, x_b), hy - th / 2, z0, max(x_a, x_b), hy + th / 2,
                d["head"] - 0.01, m_leaf, C, bevel=0.003)


def floor_rect(name, r, material, C, z=0.0, thick=0.03):
    x1, y1, x2, y2 = r
    return box(name, x1, y1, z - thick, x2, y2, z, material, C)


def build_floors_ceiling(M):
    C = coll("03_바닥")
    P = pxrect
    floors = [
        # 공용부: 포세린 타일 600×1200 (거실·주방·복도 일체)
        ("바닥_거실", P(139.5, 197.5, 263.5, 343.5), M["porcelain"], 0.0),
        ("바닥_복도", P(139.5, 141.5, 387, 197.5), M["porcelain"], 0.0),
        ("바닥_복도_안방앞", P(86.5, 141.5, 139.5, 185.5), M["porcelain"], 0.0),
        ("바닥_주방", P(162.5, 5.5, 262, 141.5), M["porcelain"], 0.0),
        ("바닥_주방_우측", P(262, 53.5, 276.5, 141.5), M["porcelain"], 0.0),
        ("바닥_팬트리", P(387, 167.5, 424.5, 197.5), M["porcelain"], 0.0),
        # 침실류: 광폭 강마루
        ("바닥_안방", P(18.5, 185.5, 139.5, 343.5), M["oak"], 0.0),
        ("바닥_드레스룸", P(18.5, 128, 86.5, 185.5), M["oak"], 0.0),
        ("바닥_서재", P(77.5, 53.5, 162.5, 141.5), M["oak"], 0.0),
        ("바닥_서재확장", P(48, 24.5, 162.5, 53.5), M["oak"], 0.0),
        ("바닥_자녀방1", P(263.5, 197.5, 343.5, 332.5), M["oak"], 0.0),
        ("바닥_자녀방2", P(343.5, 197.5, 424.5, 332.5), M["oak"], 0.0),
        # 습식
        ("바닥_안방욕실", P(18.5, 53.5, 77.5, 128), M["bath_floor"], -0.02),
        ("바닥_공용욕실", P(276.5, 76.5, 325, 145.5), M["bath_floor"], -0.02),
        ("바닥_세탁실", P(262, 5.5, 305, 53.5), M["utility"], -0.05),
        # 현관 (단차)
        ("바닥_현관", P(325, 89, 387, 145.5), M["entry_floor"], -ENTRY_DROP),
        # 비확장 유지
        ("바닥_실외기A", P(18.5, 24.5, 48, 53.5), M["outdoor_unit"], -0.05),
        ("바닥_실외기B", P(145, 5.5, 162.5, 24.5), M["outdoor_unit"], -0.05),
        ("바닥_실외기C", P(305, 5.5, 325, 53.5), M["outdoor_unit"], -0.05),
        ("바닥_대피공간", P(276.5, 53.5, 325, 76.5), M["outdoor_unit"], -0.05),
    ]
    for n, r, m, z in floors:
        floor_rect(n, r, m, C, z)

    # 슬래브 (하부 전체)
    box("슬래브", X(18.5) - 0.2, Y(343.5) - 0.2, -0.35, X(424.5) + 0.2, Y(5.5) + 0.2,
        -0.12 - 0.03, M["utility"], C)

    # 천장 (전체 한 장) — 평면/조감 렌더 시 숨김
    CC = coll("04_천장_조명")
    box("천장", X(18.5) - 0.1, Y(343.5) - 0.1, H, X(424.5) + 0.1, Y(5.5) + 0.1, H + 0.05,
        M["ceiling"], CC)


def bath_wall_tiles(M, C, r, h=H, skip=()):
    """욕실 4면 벽타일 패널 (벽 내측면에 1cm 두께)."""
    x1, y1, x2, y2 = r
    tt = 0.01
    if "s" not in skip:
        box("욕실벽타일_s", x1, y1, 0, x2, y1 + tt, h, M["bath_wall"], C)
    if "n" not in skip:
        box("욕실벽타일_n", x1, y2 - tt, 0, x2, y2, h, M["bath_wall"], C)
    if "w" not in skip:
        box("욕실벽타일_w", x1, y1, 0, x1 + tt, y2, h, M["bath_wall"], C)
    if "e" not in skip:
        box("욕실벽타일_e", x2 - tt, y1, 0, x2, y2, h, M["bath_wall"], C)


# ────────────────────────────────────────────────────────────────────────────
# 5. 가구·설비
# ────────────────────────────────────────────────────────────────────────────
def inner(r, t=T_INT, t_ext=None):
    """중심선 사각형 → 내측 마감면 (간단히 모든 면 t/2 오프셋)."""
    x1, y1, x2, y2 = r
    d = t / 2
    return x1 + d, y1 + d, x2 - d, y2 - d


def chair(name, cx, cy, ang, M, C, seat_mat=None):
    seat_mat = seat_mat or M["fabric_gray"]
    parts = [
        ((-0.22, -0.22, 0.43), (0.22, 0.22, 0.47), seat_mat),
        ((-0.22, 0.18, 0.47), (0.22, 0.22, 0.85), M["cab_oak"]),
    ]
    for i, (a, b, mm) in enumerate(parts):
        o = box(f"{name}_{i}", cx + a[0], cy + a[1], a[2], cx + b[0], cy + b[1], b[2], mm, C,
                bevel=0.008, pivot=(cx, cy), angle=ang)
    for j, (lx, ly) in enumerate([(-0.19, -0.19), (0.19, -0.19), (-0.19, 0.19), (0.19, 0.19)]):
        box(f"{name}_leg{j}", cx + lx - 0.012, cy + ly - 0.012, 0, cx + lx + 0.012,
            cy + ly + 0.012, 0.43, M["black"], C, pivot=(cx, cy), angle=ang)


def plant(name, cx, cy, M, C, h=1.4, r=0.22):
    cyl(f"{name}_화분", cx, cy, 0, 0.42, r, M["pot"], C, r2=r * 0.8)
    cyl(f"{name}_줄기", cx, cy, 0.42, h * 0.75, 0.015, M["cab_oak"], C, seg=8)
    sphere(f"{name}_잎1", cx, cy, h * 0.78, r * 1.6, M["plant"], C, sz=1.1)
    sphere(f"{name}_잎2", cx + 0.12, cy - 0.08, h * 0.62, r * 1.1, M["plant"], C)


def pendant(name, cx, cy, z, M, C):
    cyl(f"{name}_선", cx, cy, z + 0.12, H, 0.003, M["black"], C, seg=6)
    cyl(f"{name}_갓", cx, cy, z, z + 0.12, 0.13, M["black"], C, r2=0.03)
    cyl(f"{name}_광원", cx, cy, z - 0.002, z + 0.002, 0.11, M["downlight"], C)


def bed(name, x1, y1, x2, y2, head_side, M, C, accent=True):
    """head_side: 'w','e','n','s' 헤드보드 방향."""
    box(f"{name}_프레임", x1, y1, 0.08, x2, y2, 0.30, M["cab_greige"], C, bevel=0.01)
    box(f"{name}_매트리스", x1 + 0.03, y1 + 0.03, 0.30, x2 - 0.03, y2 - 0.03, 0.52,
        M["bedding"], C, bevel=0.03)
    # 이불(발치 쪽 2/3)
    if head_side in ("w", "e"):
        L = x2 - x1
        if head_side == "w":
            bx1, bx2 = x1 + L * 0.28, x2 + 0.02
            px1, px2 = x1 + 0.08, x1 + 0.45
        else:
            bx1, bx2 = x1 - 0.02, x2 - L * 0.28
            px1, px2 = x2 - 0.45, x2 - 0.08
        box(f"{name}_이불", bx1, y1 - 0.02, 0.50, bx2, y2 + 0.02, 0.56, M["bedding"], C, bevel=0.02)
        if accent:
            ax1, ax2 = (bx2 - 0.55, bx2) if head_side == "w" else (bx1, bx1 + 0.55)
            box(f"{name}_스로우", ax1, y1 - 0.03, 0.56, ax2, y2 + 0.03, 0.58,
                M["bedding_accent"], C, bevel=0.01)
        n_p = 2 if (y2 - y1) > 1.3 else 1
        for k in range(n_p):
            py1 = y1 + 0.08 + k * ((y2 - y1 - 0.16) / n_p)
            py2 = py1 + (y2 - y1 - 0.16) / n_p - 0.05
            box(f"{name}_베개{k}", px1, py1, 0.52, px2, py2, 0.66, M["bedding"], C, bevel=0.05)
        hx1, hx2 = (x1 - 0.06, x1) if head_side == "w" else (x2, x2 + 0.06)
        box(f"{name}_헤드보드", hx1, y1 - 0.05, 0.08, hx2, y2 + 0.05, 1.05, M["fabric_gray"], C,
            bevel=0.02)
    else:
        L = y2 - y1
        if head_side == "n":
            by1, by2 = y1 - 0.02, y2 - L * 0.28
            py1, py2 = y2 - 0.45, y2 - 0.08
            hy1, hy2 = y2, y2 + 0.06
        else:
            by1, by2 = y1 + L * 0.28, y2 + 0.02
            py1, py2 = y1 + 0.08, y1 + 0.45
            hy1, hy2 = y1 - 0.06, y1
        box(f"{name}_이불", x1 - 0.02, by1, 0.50, x2 + 0.02, by2, 0.56, M["bedding"], C, bevel=0.02)
        if accent:
            ay1, ay2 = (by1, by1 + 0.55) if head_side == "n" else (by2 - 0.55, by2)
            box(f"{name}_스로우", x1 - 0.03, ay1, 0.56, x2 + 0.03, ay2, 0.58,
                M["bedding_accent"], C, bevel=0.01)
        box(f"{name}_베개", x1 + 0.08, py1, 0.52, x2 - 0.08, py2, 0.66, M["bedding"], C, bevel=0.05)
        box(f"{name}_헤드보드", x1 - 0.05, hy1, 0.08, x2 + 0.05, hy2, 1.05, M["fabric_gray"], C,
            bevel=0.02)


def wardrobe(name, x1, y1, x2, y2, M, C, along="y", door_w=0.5, mat_key="cab_white"):
    """천장까지 붙박이장 + 도어 분할선(히든 손잡이)."""
    box(f"{name}_본체", x1, y1, 0, x2, y2, H - 0.005, M[mat_key], C, bevel=0.002)
    # 도어 분할 홈 (전면 방향 자동 판단: 얇은 쪽이 깊이)
    if along == "y":
        n = max(1, round((y2 - y1) / door_w))
        for k in range(1, n):
            yy = y1 + (y2 - y1) * k / n
            box(f"{name}_홈{k}", x1 - 0.002, yy - 0.002, 0.02, x2 + 0.002, yy + 0.002, H - 0.02,
                M["black"], C)
    else:
        n = max(1, round((x2 - x1) / door_w))
        for k in range(1, n):
            xx = x1 + (x2 - x1) * k / n
            box(f"{name}_홈{k}", xx - 0.002, y1 - 0.002, 0.02, xx + 0.002, y2 + 0.002, H - 0.02,
                M["black"], C)


def desk(name, x1, y1, x2, y2, M, C, top="cab_oak"):
    box(f"{name}_상판", x1, y1, 0.72, x2, y2, 0.75, M[top], C, bevel=0.004)
    box(f"{name}_다리L", x1 + 0.02, y1 + 0.02, 0, x1 + 0.05, y2 - 0.02, 0.72, M["black"], C)
    box(f"{name}_다리R", x2 - 0.05, y1 + 0.02, 0, x2 - 0.02, y2 - 0.02, 0.72, M["black"], C)


def shelf_unit(name, x1, y1, x2, y2, z1, z2, n, M, C, facing="x", books=True):
    """오픈 선반. facing='x': x 방향으로 길게 놓이고 y 쪽이 열림 / 'y': y 방향으로 길고 x 쪽이 열림."""
    t = 0.02
    if facing == "x":
        box(f"{name}_측1", x1, y1, z1, x1 + t, y2, z2, M["cab_white"], C)
        box(f"{name}_측2", x2 - t, y1, z1, x2, y2, z2, M["cab_white"], C)
    else:
        box(f"{name}_측1", x1, y1, z1, x2, y1 + t, z2, M["cab_white"], C)
        box(f"{name}_측2", x1, y2 - t, z1, x2, y2, z2, M["cab_white"], C)
    for k in range(n + 1):
        z = z1 + (z2 - z1 - t) * k / n
        box(f"{name}_선반{k}", x1, y1, z, x2, y2, z + t, M["cab_white"], C)
        if books and k < n and k % 2 == 1:
            if facing == "x":
                box(f"{name}_책{k}", x1 + 0.1, y1 + 0.03, z + t, x1 + (x2 - x1) * 0.55, y2 - 0.03,
                    z + t + 0.24, M["book"], C)
            else:
                box(f"{name}_책{k}", x1 + 0.03, y1 + 0.1, z + t, x2 - 0.03, y1 + (y2 - y1) * 0.55,
                    z + t + 0.24, M["book"], C)


def build_living(M):
    C = coll("10_거실", coll("05_가구"))
    x1, y1, x2, y2 = inner(pxrect(139.5, 197.5, 263.5, 343.5))
    y1 = Y(343.5) + T_EXT / 2
    # TV 아트월 (서측, 안방 벽) — 포세린 슬랩
    box("거실_아트월", x1, 0.1, 0, x1 + 0.02, 3.5, H, M["slab"], C)
    box("거실_TV장", x1 + 0.02, 0.55, 0.18, x1 + 0.47, 3.05, 0.52, M["cab_oak"], C, bevel=0.004)
    box("거실_TV장_간접등", x1 + 0.02, 0.6, 0.16, x1 + 0.4, 3.0, 0.18, M["led"], C)
    box("거실_TV", x1 + 0.05, 0.85, 0.85, x1 + 0.09, 2.75, 1.94, M["tv"], C, bevel=0.004)
    # 소파 (동측, 자녀방 벽) — 3.2m 모듈
    sx2 = x2 - 0.03
    sx1 = sx2 - 1.0
    sy1, sy2 = 0.2, 3.3
    box("거실_소파_베이스", sx1, sy1, 0.06, sx2, sy2, 0.40, M["fabric_sofa"], C, bevel=0.03)
    box("거실_소파_등받이", sx2 - 0.25, sy1, 0.40, sx2, sy2, 0.80, M["fabric_sofa"], C, bevel=0.06)
    for k in range(3):
        cy1 = sy1 + 0.05 + k * (sy2 - sy1 - 0.1) / 3
        cy2 = cy1 + (sy2 - sy1 - 0.1) / 3 - 0.02
        box(f"거실_소파_방석{k}", sx1 + 0.02, cy1, 0.40, sx2 - 0.26, cy2, 0.50, M["fabric_sofa"], C,
            bevel=0.04)
        box(f"거실_소파_등쿠션{k}", sx2 - 0.42, cy1 + 0.05, 0.50, sx2 - 0.24, cy2 - 0.05, 0.85,
            M["fabric_sofa"], C, bevel=0.06)
    box("거실_쿠션1", sx2 - 0.45, sy1 + 0.2, 0.5, sx2 - 0.3, sy1 + 0.6, 0.85, M["bedding_accent"], C,
        bevel=0.05)
    # 러그·테이블
    box("거실_러그", x1 + 1.1, 0.3, 0.0, sx1 + 0.4, 3.2, 0.012, M["rug"], C, bevel=0.005)
    cyl("거실_커피테이블1", 6.25, 1.95, 0.0, 0.34, 0.48, M["cab_oak"], C, seg=48, bevel=0.005)
    cyl("거실_커피테이블2", 5.65, 1.25, 0.0, 0.28, 0.30, M["counter"], C, seg=48, bevel=0.005)
    # 창가 라운지 체어 + 플로어 스탠드 + 식물
    box("거실_라운지체어_좌석", 4.55, -1.05, 0.12, 5.35, -0.3, 0.40, M["leather"], C, bevel=0.04,
        pivot=(4.95, -0.67), angle=math.radians(25))
    box("거실_라운지체어_등", 4.55, -1.05, 0.40, 5.35, -0.88, 0.85, M["leather"], C, bevel=0.04,
        pivot=(4.95, -0.67), angle=math.radians(25))
    cyl("거실_스탠드_봉", 8.15, 3.55, 0.0, 1.55, 0.01, M["black"], C, seg=8)
    cyl("거실_스탠드_베이스", 8.15, 3.55, 0.0, 0.02, 0.15, M["black"], C)
    cyl("거실_스탠드_갓", 8.15, 3.55, 1.40, 1.65, 0.20, M["curtain"], C, r2=0.16)
    plant("거실_식물", 8.05, -1.05, M, C, h=1.6)
    # 쉬어 커튼 (창 양끝에 모아둔 상태)
    for k, (a, b) in enumerate([(x1 + 0.05, x1 + 0.55), (x2 - 0.55, x2 - 0.05)]):
        box(f"거실_커튼{k}", a, y1 + 0.08, 0.02, b, y1 + 0.16, H - 0.03, M["curtain"], C, bevel=0.02)


def build_kitchen(M):
    C = coll("11_주방", coll("05_가구"))
    kx1 = X(162.5) + T_INT / 2      # 서재 벽 내측
    kx2 = X(262) - T_INT / 2        # 세탁실 벽 내측 (창측 구간)
    kx2b = X(276.5) - T_INT / 2     # 공용욕실 벽 내측
    ky_top = Y(5.5) - T_EXT / 2     # 확장된 북측 외벽 내측
    # 창측 ㅡ자 하부장 (싱크)
    box("주방_하부장", kx1, ky_top - 0.62, 0.1, kx2, ky_top, 0.87, M["cab_white"], C, bevel=0.002)
    box("주방_걸레받이", kx1, ky_top - 0.56, 0, kx2, ky_top, 0.1, M["black"], C)
    box("주방_상판", kx1, ky_top - 0.64, 0.87, kx2, ky_top, 0.90, M["counter"], C, bevel=0.002)
    box("주방_싱크볼", 6.25, ky_top - 0.52, 0.885, 7.05, ky_top - 0.1, 0.902, M["steel"], C)
    cyl("주방_수전", 6.65, ky_top - 0.06, 0.9, 1.22, 0.015, M["black"], C, seg=12)
    box("주방_수전토출", 6.64, ky_top - 0.3, 1.19, 6.66, ky_top - 0.06, 1.22, M["black"], C)
    # 좌측 키큰장 (냉장고·오븐·팬트리, 서재 벽면)
    wardrobe("주방_키큰장", kx1, 6.55, kx1 + 0.65, ky_top - 0.64, M, C, along="y", door_w=0.6)
    # 우측 키큰장 (김치냉장고·수납, 공용욕실 벽면)
    wardrobe("주방_우측키큰장", kx2b - 0.65, 6.1, kx2b, Y(53.5) - 0.06, M, C, along="y", door_w=0.6,
             mat_key="cab_greige")
    # 아일랜드 (인덕션)
    ix1, ix2, iy1, iy2 = 5.95, 8.05, 7.9, 8.8
    box("주방_아일랜드", ix1, iy1, 0.1, ix2, iy2, 0.87, M["cab_greige"], C, bevel=0.002)
    box("주방_아일랜드_상판", ix1 - 0.02, iy1 - 0.02, 0.87, ix2 + 0.02, iy2 + 0.02, 0.90,
        M["counter"], C, bevel=0.002)
    box("주방_인덕션", 6.55, 8.05, 0.90, 7.35, 8.62, 0.905, M["tv"], C)
    box("주방_천장형후드", 6.55, 8.05, 1.95, 7.35, 8.62, H, M["steel"], C, bevel=0.003)
    # 식탁 (6인용 2.0×0.9) + 의자 4 + 펜던트
    tx1, tx2, ty1, ty2 = 5.85, 7.85, 6.3, 7.2
    box("식탁_상판", tx1, ty1, 0.72, tx2, ty2, 0.75, M["cab_oak"], C, bevel=0.004)
    box("식탁_다리1", tx1 + 0.2, ty1 + 0.3, 0, tx1 + 0.28, ty2 - 0.3, 0.72, M["black"], C)
    box("식탁_다리2", tx2 - 0.28, ty1 + 0.3, 0, tx2 - 0.2, ty2 - 0.3, 0.72, M["black"], C)
    for k, cx in enumerate([6.35, 7.35]):
        chair(f"식탁의자S{k}", cx, ty1 - 0.28, math.pi, M, C)
        chair(f"식탁의자N{k}", cx, ty2 + 0.28, 0.0, M, C)
    for k, cx in enumerate([6.35, 7.35]):
        pendant(f"식탁펜던트{k}", cx, (ty1 + ty2) / 2, 1.55, M, C)


def build_master(M):
    C = coll("12_안방", coll("05_가구"))
    x1 = X(18.5) + T_EXT / 2
    x2 = X(139.5) - T_INT / 2
    y1 = Y(343.5) + T_EXT / 2
    y2 = Y(185.5) - T_INT / 2
    # 헤드보드 월 (서측)
    box("안방_헤드월패널", x1, 0.35, 0, x1 + 0.04, 3.45, 1.2, M["cab_oak"], C)
    bed("안방_킹침대", x1 + 0.12, 1.07, x1 + 2.22, 2.73, "w", M, C)
    for k, (a, b) in enumerate([(0.52, 0.97), (2.83, 3.28)]):
        box(f"안방_협탁{k}", x1 + 0.04, a, 0.38, x1 + 0.46, b, 0.55, M["cab_greige"], C, bevel=0.005)
        pendant(f"안방_펜던트{k}", x1 + 0.28, (a + b) / 2, 1.1, M, C)
    box("안방_러그", x1 + 1.3, 0.7, 0, x1 + 2.9, 3.1, 0.012, M["rug"], C, bevel=0.005)
    # 확장부 라운지 (창가)
    box("안방_라운지체어_좌석", 2.3, -1.2, 0.12, 3.05, -0.5, 0.40, M["fabric_sofa"], C, bevel=0.04,
        pivot=(2.67, -0.85), angle=math.radians(-20))
    box("안방_라운지체어_등", 2.3, -1.2, 0.40, 3.05, -1.05, 0.82, M["fabric_sofa"], C, bevel=0.04,
        pivot=(2.67, -0.85), angle=math.radians(-20))
    cyl("안방_사이드테이블", 3.45, -0.95, 0, 0.5, 0.22, M["cab_oak"], C, bevel=0.005)
    plant("안방_식물", x1 + 0.35, y1 + 0.35, M, C, h=1.2, r=0.18)
    # 화장대 (동측 벽, 거실 벽면)
    box("안방_화장대", x2 - 0.45, 0.6, 0.72, x2, 1.8, 0.76, M["cab_oak"], C, bevel=0.004)
    box("안방_화장대_거울", x2 - 0.02, 0.8, 1.0, x2, 1.6, 1.9, M["mirror"], C)
    chair("안방_화장대의자", x2 - 0.65, 1.2, math.pi / 2, M, C, seat_mat=M["fabric_sofa"])
    # 커튼
    box("안방_커튼", x1 + 0.05, y1 + 0.08, 0.02, x1 + 0.6, y1 + 0.16, H - 0.03, M["curtain"], C,
        bevel=0.02)
    box("안방_커튼2", x2 - 0.6, y1 + 0.08, 0.02, x2 - 0.05, y1 + 0.16, H - 0.03, M["curtain"], C,
        bevel=0.02)


def build_dress_bath1(M):
    C = coll("13_드레스룸_안방욕실", coll("05_가구"))
    x1 = X(18.5) + T_EXT / 2
    dx2 = X(86.5) - T_INT / 2
    dy1 = Y(185.5) + T_INT / 2
    dy2 = Y(128) - T_INT / 2
    # 드레스룸: 양측 오픈 행거장 + 중앙 서랍 아일랜드
    shelf_unit("드레스_서측", x1, dy1 + 0.05, x1 + 0.55, dy2 - 0.02, 0, H - 0.02, 5, M, C,
               facing="y", books=False)
    box("드레스_행거봉", x1 + 0.25, dy1 + 0.1, 1.75, x1 + 0.28, dy2 - 0.05, 1.78, M["black"], C)
    for k in range(9):
        yy = dy1 + 0.2 + k * 0.18
        if yy > dy2 - 0.1:
            break
        box(f"드레스_옷{k}", x1 + 0.08, yy, 0.95, x1 + 0.48, yy + 0.05, 1.72,
            M["fabric_gray"] if k % 2 else M["bedding_accent"], C, bevel=0.01)
    shelf_unit("드레스_동측", dx2 - 0.45, dy1 + 0.05, dx2, dy2 - 0.55, 0, H - 0.02, 6, M, C,
               facing="y", books=False)
    box("드레스_전신거울", dx2 - 0.02, dy2 - 0.5, 0.05, dx2, dy2 - 0.05, 1.9, M["mirror"], C)

    # 안방욕실 (샤워부스 + 세면대 + 양변기)
    C2 = coll("13b_안방욕실", coll("05_가구"))
    bx1, by1 = X(18.5) + T_EXT / 2, Y(128) + T_INT / 2
    bx2, by2 = X(77.5) - T_INT / 2, Y(53.5) - T_INT / 2
    bath_wall_tiles(M, C2, (bx1, by1, bx2, by2))
    box("안방욕실_샤워유리", bx1 + 0.01, by2 - 1.0, 0, bx2 - 0.9, by2 - 0.99, 2.0, M["glass"], C2)
    box("안방욕실_샤워수전", bx1 + 0.4, by2 - 0.06, 1.0, bx1 + 0.55, by2 - 0.01, 1.15, M["black"], C2)
    cyl("안방욕실_해바라기", bx1 + 0.5, by2 - 0.35, 2.05, 2.07, 0.13, M["black"], C2)
    box("안방욕실_해바라기암", bx1 + 0.49, by2 - 0.35, 2.06, bx1 + 0.51, by2 - 0.01, 2.08, M["black"], C2)
    box("안방욕실_젠다이", bx1 + 0.01, by2 - 1.0, 0.0, bx2 - 0.01, by2 - 0.01, 0.02, M["bath_floor"], C2)
    # 세면대 (동측 벽)
    box("안방욕실_세면장", bx2 - 0.48, by1 + 0.35, 0.45, bx2 - 0.01, by1 + 1.25, 0.82, M["cab_oak"], C2,
        bevel=0.004)
    box("안방욕실_세면상판", bx2 - 0.5, by1 + 0.33, 0.82, bx2 - 0.01, by1 + 1.27, 0.85, M["counter"], C2)
    cyl("안방욕실_세면볼", bx2 - 0.25, by1 + 0.8, 0.85, 0.95, 0.19, M["porcelain_ware"], C2, seg=40)
    box("안방욕실_거울장", bx2 - 0.14, by1 + 0.35, 1.05, bx2 - 0.01, by1 + 1.25, 1.85, M["mirror"], C2)
    box("안방욕실_거울간접등", bx2 - 0.14, by1 + 0.36, 1.03, bx2 - 0.02, by1 + 1.24, 1.05, M["led"], C2)
    # 양변기 (서측 벽, 벽걸이형)
    box("안방욕실_변기탱크", bx1 + 0.01, by1 + 0.55, 0.0, bx1 + 0.2, by1 + 1.05, 1.1, M["bath_wall"], C2)
    box("안방욕실_변기", bx1 + 0.2, by1 + 0.62, 0.3, bx1 + 0.75, by1 + 0.98, 0.42, M["porcelain_ware"], C2,
        bevel=0.05)


def build_study(M):
    C = coll("14_서재", coll("05_가구"))
    x1 = X(77.5) + T_INT / 2
    x2 = X(162.5) - T_INT / 2
    y1 = Y(141.5) + T_INT / 2
    y_win = Y(24.5) - T_EXT / 2
    nook_x1 = X(48) + 0.075
    # 창가 2인 데스크 (확장부 전체 폭)
    desk("서재_2인데스크", X(77.5) + 0.05, y_win - 0.65, x2 - 0.02, y_win - 0.02, M, C)
    chair("서재_의자1", 3.05, y_win - 0.95, math.pi, M, C)
    chair("서재_의자2", 4.25, y_win - 0.95, math.pi, M, C)
    box("서재_모니터1", 2.8, y_win - 0.2, 0.9, 3.3, y_win - 0.17, 1.2, M["tv"], C)
    box("서재_모니터2", 4.0, y_win - 0.2, 0.9, 4.5, y_win - 0.17, 1.2, M["tv"], C)
    # 확장 니치 (욕실 뒤편): 붙박이 책장
    shelf_unit("서재_니치책장", nook_x1, y_win - 0.36, X(77.5) + 0.02, y_win - 0.01, 0, H - 0.02, 6,
               M, C, facing="x")
    # 서측 벽 전면 책장
    shelf_unit("서재_벽책장", x1, y1 + 0.95, x1 + 0.35, Y(53.5) + 0.3, 0, H - 0.02, 6, M, C,
               facing="y")
    # 동측 벽 소파베드 (게스트용)
    box("서재_소파베드", x2 - 0.9, y1 + 0.75, 0.08, x2 - 0.02, y1 + 2.75, 0.45, M["fabric_gray"], C,
        bevel=0.03)
    box("서재_소파베드_등", x2 - 0.25, y1 + 0.75, 0.45, x2 - 0.02, y1 + 2.75, 0.85, M["fabric_gray"], C,
        bevel=0.05)
    box("서재_러그", x1 + 0.6, y1 + 0.9, 0, x2 - 1.0, y1 + 2.6, 0.012, M["rug"], C)


def build_kids(M):
    for idx, (rx1, rx2, door_px) in enumerate([(263.5, 343.5, 283), (343.5, 424.5, 362)], start=1):
        C = coll(f"15_자녀방{idx}", coll("05_가구"))
        x1 = X(rx1) + T_INT / 2
        x2 = X(rx2) - (T_EXT if idx == 2 else T_INT) / 2
        y1 = Y(332.5) + T_EXT / 2
        y2 = Y(197.5) - T_INT / 2
        mirror = idx == 2
        # 붙박이장: 자녀방1은 거실 쪽 벽(방음 겸), 자녀방2는 동측 외벽
        if not mirror:
            wardrobe(f"자녀방{idx}_붙박이장", x1, 0.35, x1 + 0.6, y2 - 1.05, M, C, along="y")
            bed(f"자녀방{idx}_침대", x2 - 1.12, 0.75, x2 - 0.02, 2.8, "n" if False else "s", M, C)
        else:
            wardrobe(f"자녀방{idx}_붙박이장", x2 - 0.6, 0.35, x2, y2 - 0.05, M, C, along="y")
            bed(f"자녀방{idx}_침대", x1 + 0.02, 0.75, x1 + 1.12, 2.8, "s", M, C)
        # 확장부 창가 책상 (전폭) + 상부 선반
        desk(f"자녀방{idx}_책상", x1 + 0.05, y1 + 0.05, x2 - 0.05, y1 + 0.65, M, C, top="cab_white")
        chair(f"자녀방{idx}_의자", (x1 + x2) / 2, y1 + 0.95, 0.0, M, C,
              seat_mat=M["bedding_accent"] if idx == 1 else M["fabric_gray"])
        box(f"자녀방{idx}_스탠드", x1 + 0.3, y1 + 0.15, 0.75, x1 + 0.42, y1 + 0.27, 1.15, M["black"], C)
        box(f"자녀방{idx}_러그", (x1 + x2) / 2 - 0.7, 1.0, 0, (x1 + x2) / 2 + 0.5, 2.6, 0.012, M["rug"], C)
        box(f"자녀방{idx}_커튼", x1 + 0.05, y1 + 0.08, 0.02, x1 + 0.45, y1 + 0.16, H - 0.03,
            M["curtain"], C, bevel=0.02)


def build_bath2(M):
    C = coll("16_공용욕실", coll("05_가구"))
    x1, y1 = X(276.5) + T_INT / 2, Y(145.5) + T_INT / 2
    x2, y2 = X(325) - T_INT / 2, Y(76.5) - 0.075
    bath_wall_tiles(M, C, (x1, y1, x2, y2))
    # 욕조 (북측, 기존 위치 유지)
    box("공용욕실_욕조", x1 + 0.01, y2 - 0.75, 0, x2 - 0.01, y2 - 0.01, 0.55, M["porcelain_ware"], C,
        bevel=0.02)
    box("공용욕실_욕조내부", x1 + 0.1, y2 - 0.66, 0.2, x2 - 0.1, y2 - 0.1, 0.56, M["bath_wall"], C,
        bevel=0.04)
    box("공용욕실_욕조유리", x1 + 0.01, y2 - 0.76, 0.55, x1 + 0.7, y2 - 0.75, 1.9, M["glass"], C)
    # 세면대 (서측 벽)
    box("공용욕실_세면장", x1 + 0.01, y1 + 0.55, 0.45, x1 + 0.48, y1 + 1.35, 0.82, M["cab_white"], C,
        bevel=0.004)
    box("공용욕실_세면상판", x1 + 0.01, y1 + 0.53, 0.82, x1 + 0.5, y1 + 1.37, 0.85, M["counter"], C)
    cyl("공용욕실_세면볼", x1 + 0.26, y1 + 0.95, 0.85, 0.95, 0.18, M["porcelain_ware"], C, seg=40)
    box("공용욕실_거울", x1 + 0.01, y1 + 0.55, 1.05, x1 + 0.03, y1 + 1.35, 1.85, M["mirror"], C)
    # 양변기 (동측 벽)
    box("공용욕실_변기탱크", x2 - 0.2, y1 + 0.55, 0, x2 - 0.01, y1 + 1.05, 1.1, M["bath_wall"], C)
    box("공용욕실_변기", x2 - 0.75, y1 + 0.62, 0.3, x2 - 0.2, y1 + 0.98, 0.42, M["porcelain_ware"], C,
        bevel=0.05)


def build_entry_misc(M):
    C = coll("17_현관_세탁_팬트리", coll("05_가구"))
    # 현관 신발장 (천장까지, 하부 25cm 띄움 + 간접등)
    sx1, sx2 = X(325) + 0.06, X(343.5) - 0.02
    sy1, sy2 = Y(145.5) + 0.08, Y(89) - T_EXT / 2
    box("현관_신발장", sx1, sy1, 0.25 - ENTRY_DROP, sx2, sy2, H - 0.005, M["cab_white"], C, bevel=0.002)
    box("현관_신발장_간접등", sx1 + 0.02, sy1 + 0.02, 0.23 - ENTRY_DROP, sx2 - 0.02, sy2 - 0.02,
        0.25 - ENTRY_DROP, M["led"], C)
    box("현관_벤치", X(387) - 0.42, 5.8, 0.35 - ENTRY_DROP, X(387) - 0.07, 6.9, 0.40 - ENTRY_DROP,
        M["cab_oak"], C, bevel=0.004)
    box("현관_전신거울", X(387) - 0.08, 5.8, 0.5, X(387) - 0.06, 6.9, 2.0, M["mirror"], C)
    # 중문: 3연동 슬림 슬라이딩 (다크 프레임 + 유리)
    zx1, zx2 = X(343.5), X(387) - 0.1
    zy = Y(145.5)
    n = 3
    for k in range(n):
        a = zx1 + (zx2 - zx1) * k / n
        b = zx1 + (zx2 - zx1) * (k + 1) / n
        off = (k - 1) * 0.035
        box(f"중문_{k}_프레임", a, zy - 0.02 + off, 0, b, zy + 0.02 + off, 2.1, M["frame"], C)
        box(f"중문_{k}_유리", a + 0.03, zy - 0.025 + off, 0.03, b - 0.03, zy + 0.025 + off, 2.07,
            M["glass"], C)
    box("중문_상부레일", zx1, zy - 0.08, 2.1, zx2, zy + 0.08, H, M["paint"], C)

    # 세탁실: 세탁기+건조기 직렬 + 다용도 싱크
    lx1, lx2 = X(262) + 0.06, X(305) - 0.075
    ly1, ly2 = Y(53.5) + 0.075, Y(5.5) - T_EXT / 2
    box("세탁실_세탁기", lx1 + 0.05, ly2 - 0.7, -0.05, lx1 + 0.75, ly2 - 0.02, 0.85, M["cab_white"], C,
        bevel=0.02)
    box("세탁실_건조기", lx1 + 0.05, ly2 - 0.7, 0.85, lx1 + 0.75, ly2 - 0.02, 1.7, M["cab_white"], C,
        bevel=0.02)
    cyl("세탁실_세탁기문", lx1 + 0.4, ly2 - 0.71, 0.3, 0.3001, 0.2, M["tv"], C)
    box("세탁실_싱크장", lx2 - 0.55, ly2 - 0.6, -0.05, lx2 - 0.02, ly2 - 0.02, 0.85, M["cab_greige"], C,
        bevel=0.003)
    box("세탁실_선반", lx1 + 0.02, ly1 + 0.02, 1.8, lx2 - 0.02, ly1 + 0.4, 1.83, M["cab_white"], C)

    # 팬트리 선반 (ㄷ자)
    px1, px2 = X(387) + T_INT / 2, X(424.5) - T_EXT / 2
    py1, py2 = Y(197.5) + T_INT / 2, Y(167.5) - T_EXT / 2
    shelf_unit("팬트리_북측", px1 + 0.1, py2 - 0.4, px2, py2, 0, H - 0.02, 5, M, C, facing="x")
    shelf_unit("팬트리_동측", px2 - 0.4, py1, px2, py2 - 0.4, 0, H - 0.02, 5, M, C, facing="y")


def build_ceiling_lights(M):
    C = coll("04_천장_조명")
    # 거실 라인조명 (무몰딩 천장 매입 느낌) 2줄
    for k, xx in enumerate([5.05, 7.55]):
        box(f"거실_라인조명{k}", xx - 0.02, -1.1, H - 0.005, xx + 0.02, 3.4, H, M["led"], C)
    # 복도 라인조명 1줄 (현관 → 거실)
    box("복도_라인조명", 4.4, 4.62, H - 0.005, 12.6, 4.66, H, M["led"], C)
    # 매입 다운라이트 (방별)
    spots = {
        "안방": [(1.0, -0.6), (3.3, -0.6), (3.3, 3.3), (1.0, 3.6)],
        "드레스": [(1.2, 5.1)],
        "안방욕실": [(1.0, 7.3), (1.0, 8.2)],
        "서재": [(3.5, 7.0), (3.5, 9.2), (1.5, 9.3)],
        "주방": [(5.6, 9.9), (7.9, 9.9), (8.5, 7.0), (5.4, 7.5)],
        "공용욕실": [(9.8, 6.4), (9.8, 7.4)],
        "현관": [(12.0, 6.5)],
        "자녀방1": [(9.9, 0.0), (9.9, 2.5)],
        "자녀방2": [(12.7, 0.0), (12.7, 2.5)],
        "세탁실": [(9.2, 9.6)],
        "팬트리": [(13.4, 4.2)],
    }
    for room, pts in spots.items():
        for k, (px_, py_) in enumerate(pts):
            cyl(f"매입등_{room}{k}", px_, py_, H - 0.004, H, 0.045, M["downlight"], C, seg=16)


# ────────────────────────────────────────────────────────────────────────────
# 6. 조명·카메라·렌더 설정
# ────────────────────────────────────────────────────────────────────────────
def area_light(name, x, y, z, sx, sy, power, C, color=(1.0, 0.92, 0.82)):
    ld = bpy.data.lights.new(name, type="AREA")
    ld.shape = "RECTANGLE"
    ld.size = sx
    ld.size_y = sy
    ld.energy = power
    ld.color = color
    o = bpy.data.objects.new(name, ld)
    o.location = (x, y, z)
    C.objects.link(o)
    return o


def build_lighting():
    C = coll("06_라이트")
    # 태양: 남향 (도면 아래쪽 = 남측으로 가정), 오후 햇살
    sd = bpy.data.lights.new("태양", type="SUN")
    sd.energy = 4.0
    sd.angle = math.radians(1.5)
    sd.color = (1.0, 0.95, 0.88)
    so = bpy.data.objects.new("태양", sd)
    so.rotation_euler = (math.radians(55), 0, math.radians(200))
    C.objects.link(so)
    # 실내 보조광 (천장 면광원 — 실제 조명기구가 아닌 렌더용 채움광)
    rooms = {
        "거실": pxrect(139.5, 197.5, 263.5, 343.5),
        "복도": pxrect(86.5, 141.5, 387, 197.5),
        "주방": pxrect(162.5, 5.5, 262, 141.5),
        "안방": pxrect(18.5, 185.5, 139.5, 343.5),
        "드레스": pxrect(18.5, 128, 86.5, 185.5),
        "안방욕실": pxrect(18.5, 53.5, 77.5, 128),
        "서재": pxrect(48, 24.5, 162.5, 141.5),
        "공용욕실": pxrect(276.5, 76.5, 325, 145.5),
        "현관": pxrect(325, 89, 387, 145.5),
        "자녀방1": pxrect(263.5, 197.5, 343.5, 332.5),
        "자녀방2": pxrect(343.5, 197.5, 424.5, 332.5),
        "세탁실": pxrect(262, 5.5, 305, 53.5),
    }
    for n, (x1, y1, x2, y2) in rooms.items():
        a = (x2 - x1) * (y2 - y1)
        area_light(f"채움광_{n}", (x1 + x2) / 2, (y1 + y2) / 2, H - 0.02, (x2 - x1) * 0.8,
                   (y2 - y1) * 0.8, 5 * a, C)

    w = bpy.data.worlds.new("하늘")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    set_input(bg, "Color", (0.62, 0.74, 0.92, 1))
    set_input(bg, "Strength", 1.2)


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def add_camera(name, loc, target=None, lens=18, ortho=None, rot=None):
    C = coll("07_카메라")
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.05
    cd.clip_end = 200
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    o = bpy.data.objects.new(name, cd)
    o.location = loc
    C.objects.link(o)
    if rot is not None:
        o.rotation_euler = rot
    elif target is not None:
        look_at(o, target)
    return o


CX = (X(18.5) + X(424.5)) / 2
CY = (Y(343.5) + Y(5.5)) / 2

CAMERAS = {
    # name: (loc, target, lens, ortho, (res_x, res_y), cutaway)
    "00_평면도": ((CX, CY, 30.0), None, 50, 15.2, (1800, 1560), True),
    "01_조감도": ((CX + 7.5, CY - 12.0, 15.5), (CX, CY - 0.3, 0.0), 30, None, (1920, 1280), True),
    "02_거실": ((7.75, 5.25, 1.4), (4.6, -0.6, 0.95), 16, None, (1440, 900), False),
    "03_주방식당": ((6.2, 0.2, 1.45), (7.0, 9.6, 1.0), 17, None, (1440, 900), False),
    "04_현관복도": ((11.05, 4.45, 1.55), (4.6, 4.7, 1.05), 18, None, (1440, 900), False),
    "05_안방": ((3.85, 3.7, 1.5), (0.5, 0.3, 0.8), 16, None, (1440, 900), False),
    "06_서재": ((4.7, 5.85, 1.5), (2.2, 9.5, 0.9), 16, None, (1440, 900), False),
    "07_자녀방1": ((11.0, 3.4, 1.5), (9.0, -0.8, 0.8), 16, None, (1440, 900), False),
}


def build_cameras():
    for n, (loc, tgt, lens, ortho, _res, _cut) in CAMERAS.items():
        add_camera(n, loc, tgt, lens, ortho, rot=(0, 0, 0) if ortho else None)


def build_labels(M):
    C = coll("08_라벨(평면도용)")
    font = None
    if os.path.exists(KO_FONT):
        try:
            font = bpy.data.fonts.load(KO_FONT, check_existing=True)
        except Exception as e:   # 폰트 로드 실패 시 영문 대체
            print("font load failed:", e)
    P = pxrect
    labels = [
        ("거실", P(139.5, 197.5, 263.5, 343.5), (0.0, -0.6)),
        ("주방·식당", P(162.5, 5.5, 276.5, 141.5), (-1.3, 0.35)),
        ("안방", P(18.5, 185.5, 139.5, 343.5), (0.2, -1.4)),
        ("드레스룸", P(18.5, 128, 86.5, 185.5), (0.0, 0.0)),
        ("안방욕실", P(18.5, 53.5, 77.5, 128), (0.0, -0.3)),
        ("서재·게스트", P(77.5, 53.5, 162.5, 141.5), (0.0, -0.3)),
        ("세탁실", P(262, 5.5, 305, 53.5), (0.0, -0.4)),
        ("공용욕실", P(276.5, 76.5, 325, 145.5), (0.0, -0.4)),
        ("현관", P(343.5, 89, 387, 145.5), (0.0, 0.0)),
        ("자녀방1", P(263.5, 197.5, 343.5, 332.5), (0.0, -0.1)),
        ("자녀방2", P(343.5, 197.5, 424.5, 332.5), (0.0, -0.1)),
        ("팬트리", P(387, 167.5, 424.5, 197.5), (0.0, 0.0)),
    ]
    for name, (x1, y1, x2, y2), (ox, oy) in labels:
        dims = f"{x2 - x1:.2f}×{y2 - y1:.2f}m"
        for k, (txt, size, dy, mm) in enumerate([(name, 0.36, 0.14, M["label"]),
                                                 (dims, 0.22, -0.24, M["label_sub"])]):
            cu = bpy.data.curves.new(f"라벨_{name}_{k}", type="FONT")
            cu.body = txt
            if font:
                cu.font = font
            cu.size = size
            cu.align_x = "CENTER"
            cu.align_y = "CENTER"
            o = bpy.data.objects.new(f"라벨_{name}_{k}", cu)
            o.location = ((x1 + x2) / 2 + ox, (y1 + y2) / 2 + oy + dy, H + 0.3)
            o.data.materials.append(mm)
            o.visible_shadow = False
            C.objects.link(o)
    return font


def render_settings(quick=False):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24 if quick else 96
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.05 if quick else 0.02
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    sc.cycles.max_bounces = 8
    sc.cycles.diffuse_bounces = 4
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 6
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 1.0
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "None"):
        try:
            sc.view_settings.look = look
            break
        except TypeError:
            continue
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "PNG"


def set_visibility(cutaway):
    """평면/조감: 천장·채움광 숨기고 라벨 표시 / 실내: 반대."""
    ceil = bpy.data.collections["04_천장_조명"]
    labels = bpy.data.collections["08_라벨(평면도용)"]
    for o in ceil.objects:
        o.hide_render = cutaway
    for o in labels.objects:
        o.hide_render = not cutaway
    for o in bpy.data.collections["06_라이트"].objects:
        if o.name.startswith("채움광"):
            o.hide_render = cutaway


def render_all(quick=False, only=None):
    os.makedirs(RENDER_DIR, exist_ok=True)
    sc = bpy.context.scene
    for n, (_loc, _tgt, _lens, ortho, (rx, ry), cut) in CAMERAS.items():
        if only and n not in only:
            continue
        sc.camera = bpy.data.objects[n]
        sc.render.resolution_x = rx
        sc.render.resolution_y = ry
        sc.render.resolution_percentage = 40 if quick else 100
        set_visibility(cut)
        # 평면도: 위에서 오는 균일광 → 태양 수직, 노출 보정
        sun = bpy.data.objects["태양"]
        if ortho:
            sun.rotation_euler = (math.radians(20), 0, math.radians(200))
            sc.view_settings.exposure = -1.3
        else:
            sun.rotation_euler = (math.radians(55), 0, math.radians(200))
            sc.view_settings.exposure = -0.6 if not cut else -0.5
        sc.render.filepath = os.path.join(RENDER_DIR, f"{n}.png")
        print("render:", n, flush=True)
        bpy.ops.render.render(write_still=True)
    set_visibility(False)
    sc.camera = bpy.data.objects["02_거실"]


# ────────────────────────────────────────────────────────────────────────────
# 7. 메인
# ────────────────────────────────────────────────────────────────────────────
def build():
    reset_scene()
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.length_unit = "METERS"
    M = build_materials()
    build_architecture(M)
    build_openings(M)
    build_floors_ceiling(M)
    build_living(M)
    build_kitchen(M)
    build_master(M)
    build_dress_bath1(M)
    build_study(M)
    build_kids(M)
    build_bath2(M)
    build_entry_misc(M)
    build_ceiling_lights(M)
    build_lighting()
    build_cameras()
    font = build_labels(M)
    render_settings()
    set_visibility(False)
    sc.camera = bpy.data.objects["02_거실"]
    return font


def _argv():
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1:]
    return sys.argv[1:]


if __name__ == "__main__":
    args = _argv()
    font = build()
    only = None
    for a in args:
        if a.startswith("--only="):
            only = set(a.split("=", 1)[1].split(","))
    if "--render" in args or "--save" in args:
        if font is not None:
            try:
                font.pack()
            except Exception as e:
                print("font pack failed:", e)
        bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH, compress=True)
        print("saved:", BLEND_PATH)
    if "--render" in args:
        render_settings(quick="--quick" in args)
        render_all(quick="--quick" in args, only=only)
