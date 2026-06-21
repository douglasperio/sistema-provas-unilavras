"""Teste ponta a ponta do omr.py com uma página de gabarito sintética."""
import random

import cv2
import numpy as np
import qrcode

import omr

PX = 10  # px/mm da folha sintética
TOKEN = 'abc12345-1111-2222-3333-444455556666'


def desenhar_pagina(escolhas, n_opts_rows, max_opts):
    """Página A4 (210x297mm) com cabeçalho+QR e a grade GradeOMR."""
    num_q = len(n_opts_rows)
    grid_h = 2 * omr.REG + omr.HDR + num_q * omr.ROW
    pw, ph = int(210 * PX), int(297 * PX)
    pg = np.full((ph, pw), 255, np.uint8)

    # QR no topo direito (como no cabeçalho do PDF, 28mm)
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(TOKEN)
    qr.make(fit=True)
    qimg = np.array(qr.make_image(fill_color='black', back_color='white').convert('L'))
    qpx = int(28 * PX)
    qimg = cv2.resize(qimg, (qpx, qpx), interpolation=cv2.INTER_NEAREST)
    qx, qy = int(165 * PX), int(12 * PX)
    pg[qy:qy + qpx, qx:qx + qpx] = qimg

    # grade: começa em x=14mm (margem), y=55mm
    gx0, gy0 = 14.0, 55.0
    reg = int(omr.REG * PX)

    def mm(x, y):  # mm da grade -> px da página
        return int((gx0 + x) * PX), int((gy0 + y) * PX)

    W, H = omr.GRID_W, grid_h
    # 4 marcas de registro
    for cx, cy in [(0, 0), (W - omr.REG, 0), (0, H - omr.REG), (W - omr.REG, H - omr.REG)]:
        x, y = mm(cx, cy)
        pg[y:y + reg, x:x + reg] = 0

    # moldura da área interna + cabeçalho cinza
    x0, y0 = mm(omr.REG, omr.REG)
    x1, y1 = mm(W - omr.REG, H - omr.REG)
    cv2.rectangle(pg, (x0, y0), (x1, y1), 0, 2)
    pg[y0:y0 + int(omr.HDR * PX), x0:x1] = 238

    cell_w = (W - 2 * omr.REG - omr.NUM_W) / max_opts
    cell_sz = min(cell_w, omr.ROW) * 0.70
    half = int(cell_sz / 2 * PX)

    for irow in range(num_q):
        cy_mm = omr.REG + omr.HDR + irow * omr.ROW + omr.ROW / 2
        for icol in range(max_opts):
            cx_mm = omr.REG + omr.NUM_W + icol * cell_w + cell_w / 2
            cx, cy = mm(cx_mm, cy_mm)
            if icol >= n_opts_rows[irow]:
                pg[cy - half:cy + half, cx - half:cx + half] = 170  # célula inativa
                continue
            cv2.rectangle(pg, (cx - half, cy - half), (cx + half, cy + half), 0, 2)
            if escolhas[irow] == icol:
                pg[cy - half + 2:cy + half - 2, cx - half + 2:cx + half - 2] = 40
    return pg


def fotografar(pg, rot_deg, persp):
    pad = 300
    img = cv2.copyMakeBorder(pg, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=230)
    h, w = img.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rot_deg, 0.8)
    img = cv2.warpAffine(img, M, (w, h), borderValue=230)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dx = persp * w
    dst = np.float32([[dx, 0], [w - dx * 0.3, dx * 0.5], [w, h], [0, h - dx * 0.4]])
    img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (w, h),
                              borderValue=230)
    grad = np.tile(np.linspace(0.78, 1.05, w), (h, 1))
    img = np.clip(img * grad + np.random.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes()


def run(seed, rot, persp, num_q=15, max_opts=5):
    random.seed(seed)
    np.random.seed(seed)
    n_opts_rows = [max_opts] * num_q
    n_opts_rows[7] = 0           # questão dissertativa
    n_opts_rows[3] = 4           # questão com menos alternativas
    escolhas = [random.randrange(n) if n else None for n in n_opts_rows]
    escolhas[10] = None          # deixada em branco

    pg = desenhar_pagina(escolhas, n_opts_rows, max_opts)
    foto = fotografar(pg, rot, persp)

    lay = {'num_questoes': num_q, 'max_opts': max_opts, 'all_vf': False,
           'n_opts_rows': n_opts_rows}
    res = omr.processar_foto(foto, lambda t: lay if t == TOKEN else None)
    assert res['token'] == TOKEN

    letras = 'ABCDEFGHIJ'
    esperado = [letras[e] if e is not None else None for e in escolhas]
    return {i + 1: (esperado[i], res['marcacoes'][i])
            for i in range(num_q) if res['marcacoes'][i] != esperado[i]}


total = 0
for seed, rot, persp in [(1, 0, 0.0), (2, 6, 0.05), (3, -10, 0.07),
                         (4, 90, 0.04), (5, 178, 0.05), (6, 20, 0.08)]:
    try:
        erros = run(seed, rot, persp)
        status = 'OK' if not erros else 'ERROS: %s' % erros
        total += len(erros)
    except Exception as e:
        status = 'FALHA: %s' % e
        total += 99
    print('rot=%4d persp=%.2f -> %s' % (rot, persp, status))

print('\nTOTAL DE ERROS:', total)
