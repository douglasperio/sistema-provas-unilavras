"""
Leitura automática da grade de gabarito (OMR) com OpenCV.

Pipeline:
  1. Decodifica o QR Code da folha (token -> RespostaAluno/versão).
  2. Localiza as 4 marcas de registro (quadrados pretos) nos cantos da grade.
  3. Corrige perspectiva/rotação da foto (warp para o plano da grade em mm).
  4. Lê o preenchimento dos quadradinhos e devolve as respostas por linha.

A geometria espelha a classe GradeOMR em app.py (gerar_pdf_aplicacao):
  - Largura da grade = largura útil do A4 = 210 - 2*14 = 182mm
  - REG = 8mm (marcas de registro nos 4 cantos; canto EXTERNO = canto da grade)
  - HDR = 7mm (cabeçalho), ROW = 7mm por questão, NUM_W = 9mm
  - cell_w = (W - 2*REG - NUM_W) / max_opts
  - célula (quadradinho) = min(cell_w, ROW) * 0.70, centrada na coluna/linha
NÃO altere GradeOMR sem atualizar este arquivo (e vice-versa).
"""
import base64

import cv2
import numpy as np

# -- Geometria (mm) - deve coincidir com GradeOMR -------------------
GRID_W = 182.0
REG = 8.0
HDR = 7.0
ROW = 7.0
NUM_W = 9.0

PX_MM = 8.0          # resolução do warp (px por mm)
DARK_THRESH = 160    # pixel "escuro" na imagem normalizada
FRAC_FILLED = 0.45   # fração mínima de pixels escuros p/ "preenchido"
FRAC_GAP = 0.20      # vantagem mínima sobre a 2ª opção


class OMRError(Exception):
    """Erro de leitura com mensagem amigável para o professor."""


def _resize_max(img, max_dim=2200):
    h, w = img.shape[:2]
    s = max_dim / max(h, w)
    if s < 1.0:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return img


def _decode_qr(gray):
    det = cv2.QRCodeDetector()
    for scale in (1.0, 1.5, 0.5, 2.0):
        g = gray if scale == 1.0 else cv2.resize(gray, None, fx=scale, fy=scale)
        data, pts, _ = det.detectAndDecode(g)
        if data:
            return data.strip(), (pts.reshape(-1, 2) / scale)
    raise OMRError('QR Code não encontrado na foto. Enquadre a folha inteira, '
                   'bem iluminada e sem reflexos.')


def _find_corner_markers(gray):
    """Encontra quadrados pretos sólidos candidatos a marcas de registro."""
    h, w = gray.shape
    # Flat-field + limiar global (threshold adaptativo esvaziaria quadrados grandes)
    bg = cv2.GaussianBlur(gray, (0, 0), max(h, w) / 40.0)
    norm = np.clip(cv2.divide(gray, bg, scale=210), 0, 255).astype(np.uint8)
    thr = ((norm < 130) * 255).astype(np.uint8)
    # Abertura: apaga linhas finas (moldura da grade encosta nas marcas de
    # registro no PDF) para que cada marca vire um quadrado isolado.
    k = max(3, int(round(min(h, w) / 300.0)))
    thr = cv2.morphologyEx(thr, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))

    contours, hierarchy = cv2.findContours(thr, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        raise OMRError('Marcas de registro não encontradas.')
    hierarchy = hierarchy[0]

    img_area = h * w
    cands = []
    for i, c in enumerate(contours):
        if hierarchy[i][3] != -1:
            continue
        area = cv2.contourArea(c)
        if not (img_area * 0.00005 < area < img_area * 0.01):
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.05 * peri, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        # sólido: sem buracos relevantes (descarta padrões internos do QR)
        if hierarchy[i][2] != -1:
            hole = cv2.contourArea(contours[hierarchy[i][2]])
            if hole > area * 0.05:
                continue
        (_, _), (rw, rh), _ = cv2.minAreaRect(c)
        if rw == 0 or rh == 0 or not (0.5 < rw / rh < 2.0):
            continue
        if area / (rw * rh) < 0.85:
            continue
        cands.append(approx.reshape(4, 2).astype(np.float64))

    if len(cands) < 4:
        raise OMRError('Marcas dos cantos não encontradas (%d/4). Fotografe a '
                       'página do gabarito inteira, sem cortar os cantos.' % len(cands))
    return cands


def _pick_grid_quad(cands, qr_center):
    """Escolhe as 4 marcas que formam o maior quadrilátero e ordena
    TL, TR, BR, BL. O QR fica no cabeçalho, acima e à direita da grade -
    a marca mais próxima dele é a do canto superior DIREITO (TR)."""
    from itertools import combinations
    centers = np.array([c.mean(axis=0) for c in cands])
    areas = np.array([cv2.contourArea(c.astype(np.float32)) for c in cands])

    best, best_area = None, 0.0
    for idx in combinations(range(len(cands)), 4):
        a = areas[list(idx)]
        if a.max() > a.min() * 4.0:
            continue
        pts = centers[list(idx)].astype(np.float32)
        hull = cv2.convexHull(pts)
        if len(hull) != 4:
            continue
        area = cv2.contourArea(hull)
        if area > best_area:
            best_area, best = area, list(idx)
    if best is None:
        raise OMRError('Não foi possível identificar os 4 cantos da grade.')

    quad_cands = [cands[i] for i in best]
    quad_centers = centers[best]
    centroid = quad_centers.mean(axis=0)

    # canto EXTERNO de cada marca = vértice mais distante do centroide da grade
    outer = []
    for c in quad_cands:
        d = np.linalg.norm(c - centroid, axis=1)
        outer.append(c[d.argmax()])
    outer = np.array(outer)

    # ordena ciclicamente e garante sentido horário em coords de imagem
    ang = np.arctan2(outer[:, 1] - centroid[1], outer[:, 0] - centroid[0])
    outer = outer[np.argsort(ang)]
    v1, v2 = outer[1] - outer[0], outer[2] - outer[1]
    if v1[0] * v2[1] - v1[1] * v2[0] < 0:
        outer = outer[::-1]

    # TR = marca mais próxima do QR; roda para que TR fique no índice 1
    d_qr = np.linalg.norm(outer - qr_center, axis=1)
    tr = int(d_qr.argmin())
    outer = np.roll(outer, 1 - tr, axis=0)
    return outer.astype(np.float32)


def _warp(gray, quad, grid_h_mm):
    W, H = int(GRID_W * PX_MM), int(grid_h_mm * PX_MM)
    dst = np.array([[0, 0], [W, 0], [W, H], [0, H]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(gray, M, (W, H))


def _normalize(warp):
    bg = cv2.GaussianBlur(warp, (0, 0), 25)
    norm = cv2.divide(warp, bg, scale=210)
    return np.clip(norm, 0, 255).astype(np.uint8)


def _layout(num_questoes, max_opts):
    """Centros (mm) das células por linha/coluna, e tamanho da célula."""
    cell_w = (GRID_W - 2 * REG - NUM_W) / max_opts
    cell_sz = min(cell_w, ROW) * 0.70
    grid_h = 2 * REG + HDR + num_questoes * ROW
    rows_y = [REG + HDR + i * ROW + ROW / 2 for i in range(num_questoes)]
    cols_x = [REG + NUM_W + i * cell_w + cell_w / 2 for i in range(max_opts)]
    return grid_h, rows_y, cols_x, cell_sz


def _read_cells(norm, rows_y, cols_x, cell_sz, n_opts_rows):
    """Lê o preenchimento. Retorna lista (por linha) de índice escolhido ou None."""
    r = max(2, int(cell_sz / 2 * 0.70 * PX_MM))
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    disc = (xx * xx + yy * yy) <= r * r
    H, W = norm.shape

    escolhas, scores = [], []
    for irow, cy_mm in enumerate(rows_y):
        n_opts = n_opts_rows[irow]
        cy = int(cy_mm * PX_MM)
        fr = []
        for icol in range(n_opts):
            cx = int(cols_x[icol] * PX_MM)
            y0, y1 = max(0, cy - r), min(H, cy + r + 1)
            x0, x1 = max(0, cx - r), min(W, cx + r + 1)
            patch = norm[y0:y1, x0:x1]
            d = disc[:patch.shape[0], :patch.shape[1]]
            fr.append(float((patch[d] < DARK_THRESH).mean()) if patch.size else 0.0)
        scores.append([round(f, 2) for f in fr])
        if not fr:
            escolhas.append(None)        # dissertativa
            continue
        fr = np.array(fr)
        i = int(fr.argmax())
        second = float(np.delete(fr, i).max()) if len(fr) > 1 else 0.0
        if fr[i] >= FRAC_FILLED and (fr[i] - second) >= FRAC_GAP:
            escolhas.append(i)
        else:
            escolhas.append(None)        # em branco ou marcação dupla
    return escolhas, scores


def _debug_image(norm, rows_y, cols_x, cell_sz, n_opts_rows, escolhas):
    dbg = cv2.cvtColor(norm, cv2.COLOR_GRAY2BGR)
    half = int(cell_sz / 2 * PX_MM)
    for irow, cy_mm in enumerate(rows_y):
        cy = int(cy_mm * PX_MM)
        for icol in range(n_opts_rows[irow]):
            cx = int(cols_x[icol] * PX_MM)
            sel = escolhas[irow] == icol
            cor = (0, 180, 0) if sel else (0, 0, 230)
            cv2.rectangle(dbg, (cx - half, cy - half), (cx + half, cy + half),
                          cor, 3 if sel else 1)
    ok, buf = cv2.imencode('.jpg', dbg, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return base64.b64encode(buf.tobytes()).decode('ascii') if ok else None


def processar_foto(file_bytes, layout_lookup):
    """Processa a foto da página de gabarito.

    layout_lookup(token) -> dict com:
        num_questoes, max_opts, all_vf (bool), n_opts_rows (lista por linha)
    ou None se o token não existir.

    Retorna dict: token, marcacoes (lista por linha: letra ou None),
    scores, debug_jpeg_b64.
    """
    arr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise OMRError('Não foi possível ler a imagem enviada.')
    img = _resize_max(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    token, qr_pts = _decode_qr(gray)
    lay = layout_lookup(token)
    if not lay:
        raise OMRError('Folha não reconhecida: token do QR não existe no sistema.')

    num_q = lay['num_questoes']
    max_opts = lay['max_opts']
    grid_h, rows_y, cols_x, cell_sz = _layout(num_q, max_opts)

    cands = _find_corner_markers(gray)
    quad = _pick_grid_quad(cands, qr_pts.mean(axis=0))
    warp = _warp(gray, quad, grid_h)
    norm = _normalize(warp)

    escolhas, scores = _read_cells(norm, rows_y, cols_x, cell_sz, lay['n_opts_rows'])

    letras = 'VF' if (max_opts == 2 and lay.get('all_vf')) else 'ABCDEFGHIJ'
    marcacoes = [letras[i] if i is not None else None for i in escolhas]
    debug = _debug_image(norm, rows_y, cols_x, cell_sz, lay['n_opts_rows'], escolhas)

    return {
        'token': token,
        'marcacoes': marcacoes,
        'scores': scores,
        'debug_jpeg_b64': debug,
    }
