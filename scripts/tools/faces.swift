// 画像（複数可）の顔の位置を Apple Vision で調べ、1行に1枚ずつ JSON で出す。
// 出力: {"file": ..., "w": 幅, "h": 高さ, "faces": [[x0, y0, x1, y1], ...]}（左上原点の px）
import Vision
import AppKit
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("{\"file\":\"\(path)\",\"error\":1}"); continue }
    let w = Double(cg.width), h = Double(cg.height)
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(cgImage: cg).perform([req])
    let boxes = (req.results ?? []).map { f -> String in
        let b = f.boundingBox
        return String(format: "[%.0f,%.0f,%.0f,%.0f]", b.minX * w, (1 - b.maxY) * h, b.maxX * w, (1 - b.minY) * h)
    }
    print("{\"file\":\"\(path)\",\"w\":\(Int(w)),\"h\":\(Int(h)),\"faces\":[\(boxes.joined(separator: ","))]}")
}
