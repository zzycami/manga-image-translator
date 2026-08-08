#!/usr/bin/env swift
/**
 Mac Vision OCR spike vs MIT stages JSON (iOS-capable path; zero model download).

 Usage:
   swift tools/client_pipeline/bench_vision_ocr_mac.swift \
     --out result/bench_vision_ocr_mac/<ts> \
     --stages-dir result/bench_mit_stages_ab/simple_sort_20260808_205647/baseline \
     img1.jpg img2.jpg ...
 */
import Foundation
import Vision
import AppKit
import CoreGraphics
import ImageIO

struct Box: Codable {
    var x: Double
    var y: Double
    var w: Double
    var h: Double
}

struct VisionRegion: Codable {
    var sourceText: String
    var boundingBox: Box
    var confidence: Float
}

struct PageCompare: Codable {
    var image: String
    var visionMs: Double
    var visionCount: Int
    var mitCount: Int
    var meanBoxIouMatched: Double
    var ocrExactRate: Double
    var ocrSoftRate: Double
    var unmatchedMit: Int
    var unmatchedVision: Int
    var visionTexts: [String]
    var mitTexts: [String]
}

func loadCGImage(url: URL) -> (CGImage, Int, Int)? {
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
          let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else { return nil }
    return (cg, cg.width, cg.height)
}

func scaleCGImage(_ cg: CGImage, factor: CGFloat) -> CGImage? {
    let w = Int(CGFloat(cg.width) * factor)
    let h = Int(CGFloat(cg.height) * factor)
    guard w > 0, h > 0 else { return nil }
    let cs = CGColorSpaceCreateDeviceRGB()
    guard let ctx = CGContext(
        data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
        space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else { return nil }
    ctx.interpolationQuality = .high
    ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
    return ctx.makeImage()
}

func runVision(cg: CGImage, scale: CGFloat = 1.0) throws -> (regions: [VisionRegion], ms: Double) {
    let work = scale > 1.001 ? (scaleCGImage(cg, factor: scale) ?? cg) : cg
    let scaleBack = Double(cg.width) / Double(work.width)
    var out: [VisionRegion] = []
    let req = VNRecognizeTextRequest { request, _ in
        guard let obs = request.results as? [VNRecognizedTextObservation] else { return }
        let w = work.width
        let h = work.height
        for o in obs {
            guard let cand = o.topCandidates(1).first else { continue }
            let bb = o.boundingBox
            // Vision: origin bottom-left, normalized → page coords of original
            let x = Double(bb.origin.x) * Double(w) * scaleBack
            let y = (1.0 - Double(bb.origin.y) - Double(bb.height)) * Double(h) * scaleBack
            let bw = Double(bb.width) * Double(w) * scaleBack
            let bh = Double(bb.height) * Double(h) * scaleBack
            out.append(VisionRegion(
                sourceText: cand.string,
                boundingBox: Box(x: x, y: y, w: bw, h: bh),
                confidence: cand.confidence
            ))
        }
    }
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    req.minimumTextHeight = 0.008
    req.recognitionLanguages = ["ja-JP"]
    if #available(macOS 13.0, *) {
        req.automaticallyDetectsLanguage = false
    }

    let t0 = CFAbsoluteTimeGetCurrent()
    let handler = VNImageRequestHandler(cgImage: work, options: [:])
    try handler.perform([req])
    let ms = (CFAbsoluteTimeGetCurrent() - t0) * 1000
    return (out, ms)
}

func iou(_ a: Box, _ b: Box) -> Double {
    let ax2 = a.x + a.w, ay2 = a.y + a.h
    let bx2 = b.x + b.w, by2 = b.y + b.h
    let ix1 = max(a.x, b.x), iy1 = max(a.y, b.y)
    let ix2 = min(ax2, bx2), iy2 = min(ay2, by2)
    let iw = max(0, ix2 - ix1), ih = max(0, iy2 - iy1)
    let inter = iw * ih
    let uni = a.w * a.h + b.w * b.h - inter
    return uni > 0 ? inter / uni : 0
}

func softMatch(_ a: String, _ b: String) -> Bool {
    let na = a.replacingOccurrences(of: "\\s", with: "", options: .regularExpression)
    let nb = b.replacingOccurrences(of: "\\s", with: "", options: .regularExpression)
    if na.isEmpty || nb.isEmpty { return false }
    if na == nb { return true }
    if na.contains(nb) || nb.contains(na) { return true }
    // char Jaccard for CJK short strings
    let sa = Set(na), sb = Set(nb)
    let inter = sa.intersection(sb).count
    let uni = sa.union(sb).count
    return uni > 0 && Double(inter) / Double(uni) >= 0.6
}

struct MitRegion: Decodable {
    var sourceText: String?
    var boundingBox: Box?
}

struct MitStages: Decodable {
    var regions: [MitRegion]
    var imageWidth: Int?
    var imageHeight: Int?
}

func loadMit(url: URL) throws -> [VisionRegion] {
    let data = try Data(contentsOf: url)
    let stages = try JSONDecoder().decode(MitStages.self, from: data)
    return stages.regions.compactMap { r in
        guard let t = r.sourceText, let b = r.boundingBox else { return nil }
        return VisionRegion(sourceText: t, boundingBox: b, confidence: 1)
    }
}

func compare(vision: [VisionRegion], mit: [VisionRegion]) -> (
    meanIou: Double, exact: Double, soft: Double, unmatchedMit: Int, unmatchedVision: Int
) {
    var usedV = Set<Int>()
    var ious: [Double] = []
    var exactN = 0
    var softN = 0
    var matched = 0
    for m in mit {
        var bestI = -1
        var best = 0.0
        for (i, v) in vision.enumerated() where !usedV.contains(i) {
            let s = iou(m.boundingBox, v.boundingBox)
            if s > best { best = s; bestI = i }
        }
        if bestI >= 0 && best >= 0.1 {
            usedV.insert(bestI)
            ious.append(best)
            matched += 1
            let vt = vision[bestI].sourceText
            if vt == m.sourceText { exactN += 1 }
            if softMatch(vt, m.sourceText) { softN += 1 }
        }
    }
    let mean = ious.isEmpty ? 0 : ious.reduce(0, +) / Double(ious.count)
    let denom = max(mit.count, 1)
    return (
        mean,
        Double(exactN) / Double(denom),
        Double(softN) / Double(denom),
        mit.count - matched,
        vision.count - usedV.count
    )
}

func argValue(_ args: [String], _ name: String) -> String? {
    guard let i = args.firstIndex(of: name), i + 1 < args.count else { return nil }
    return args[i + 1]
}

let args = Array(CommandLine.arguments.dropFirst())
guard let outStr = argValue(args, "--out"), let stagesDirStr = argValue(args, "--stages-dir") else {
    fputs("need --out and --stages-dir and image paths\n", stderr)
    exit(2)
}
let scale: CGFloat = {
    if let s = argValue(args, "--scale"), let v = Double(s) { return CGFloat(v) }
    return 2.0
}()
let outRoot = URL(fileURLWithPath: outStr, isDirectory: true)
let stagesDir = URL(fileURLWithPath: stagesDirStr, isDirectory: true)
try FileManager.default.createDirectory(at: outRoot, withIntermediateDirectories: true)

let images = args.filter { !$0.hasPrefix("--") && $0 != outStr && $0 != stagesDirStr && args[args.firstIndex(of: $0)! - 1] != "--out" && args[args.firstIndex(of: $0)! - 1] != "--stages-dir" }
// simpler: collect trailing paths that exist as files
var imagePaths: [String] = []
var i = 0
while i < args.count {
    let a = args[i]
    if a == "--out" || a == "--stages-dir" || a == "--scale" { i += 2; continue }
    if a.hasPrefix("--") { i += 1; continue }
    imagePaths.append(a)
    i += 1
}

var pages: [PageCompare] = []
for path in imagePaths {
    let url = URL(fileURLWithPath: path)
    let stem = url.deletingPathExtension().lastPathComponent
    // map page_work.jpg under 005_005/ → 005_005.stages.json
    let parent = url.deletingLastPathComponent().lastPathComponent
    let stagesName = parent.contains("_") ? "\(parent).stages.json" : "\(stem).stages.json"
    let stagesURL = stagesDir.appendingPathComponent(stagesName)
    guard let (cg, _, _) = loadCGImage(url: url) else {
        fputs("fail load \(path)\n", stderr)
        continue
    }
    let mit: [VisionRegion]
    do { mit = try loadMit(url: stagesURL) } catch {
        fputs("fail mit \(stagesURL.path): \(error)\n", stderr)
        continue
    }
    let (vision, ms) = try runVision(cg: cg, scale: scale)
    let c = compare(vision: vision, mit: mit)
    let page = PageCompare(
        image: path,
        visionMs: (ms * 10).rounded() / 10,
        visionCount: vision.count,
        mitCount: mit.count,
        meanBoxIouMatched: (c.meanIou * 1000).rounded() / 1000,
        ocrExactRate: (c.exact * 1000).rounded() / 1000,
        ocrSoftRate: (c.soft * 1000).rounded() / 1000,
        unmatchedMit: c.unmatchedMit,
        unmatchedVision: c.unmatchedVision,
        visionTexts: vision.map(\.sourceText),
        mitTexts: mit.map(\.sourceText)
    )
    pages.append(page)
    let pageDir = outRoot.appendingPathComponent(parent, isDirectory: true)
    try FileManager.default.createDirectory(at: pageDir, withIntermediateDirectories: true)
    let enc = JSONEncoder()
    enc.outputFormatting = [.prettyPrinted, .sortedKeys]
    try enc.encode(vision).write(to: pageDir.appendingPathComponent("vision_regions.json"))
    try enc.encode(page).write(to: pageDir.appendingPathComponent("compare.json"))
    print("\(parent): vision=\(page.visionCount) mit=\(page.mitCount) ms=\(page.visionMs) iou=\(page.meanBoxIouMatched) exact=\(page.ocrExactRate) soft=\(page.ocrSoftRate)")
}

let summary: [String: Any] = [
    "engine": "VNRecognizeTextRequest accurate ja-JP",
    "scale": Double(scale),
    "pages": pages.map { p -> [String: Any] in
        [
            "image": p.image,
            "visionMs": p.visionMs,
            "visionCount": p.visionCount,
            "mitCount": p.mitCount,
            "meanBoxIouMatched": p.meanBoxIouMatched,
            "ocrExactRate": p.ocrExactRate,
            "ocrSoftRate": p.ocrSoftRate,
            "unmatchedMit": p.unmatchedMit,
            "unmatchedVision": p.unmatchedVision,
        ]
    },
    "visionMsSum": pages.map(\.visionMs).reduce(0, +),
    "passHint": "soft OCR >=0.7 and region count within 50% of MIT for most pages",
]
let data = try JSONSerialization.data(withJSONObject: summary, options: [.prettyPrinted, .sortedKeys])
try data.write(to: outRoot.appendingPathComponent("summary.json"))
print("wrote \(outRoot.path)/summary.json")
