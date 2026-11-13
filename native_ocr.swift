// Local OCR adapter. Uses only the built-in Apple Vision framework.
// Invocation: swift native_ocr.swift /absolute/path/to/generated-page.png
import Foundation
import Vision
import ImageIO

func boxJSON(_ box: CGRect) -> [String: Double] {
    return ["x": Double(box.minX), "y": Double(1 - box.maxY),
            "width": Double(box.width), "height": Double(box.height)]
}

do {
    guard CommandLine.arguments.count == 2 else {
        throw NSError(domain: "FormBridgeOCR", code: 1)
    }
    let url = URL(fileURLWithPath: CommandLine.arguments[1])
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw NSError(domain: "FormBridgeOCR", code: 2)
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["en-US"]
    request.usesLanguageCorrection = false
    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])
    let expression = try NSRegularExpression(pattern: "\\S+")
    var lines: [[String: Any]] = []
    for observation in request.results ?? [] {
        guard let recognized = observation.topCandidates(1).first else { continue }
        let text = recognized.string
        var words: [[String: Any]] = []
        let fullRange = NSRange(text.startIndex..<text.endIndex, in: text)
        for match in expression.matches(in: text, range: fullRange) {
            guard let range = Range(match.range, in: text),
                  let rectangle = try recognized.boundingBox(for: range) else { continue }
            var word: [String: Any] = boxJSON(rectangle.boundingBox)
            word["text"] = String(text[range])
            words.append(word)
        }
        var line: [String: Any] = boxJSON(observation.boundingBox)
        line["text"] = text
        line["words"] = words
        lines.append(line)
    }
    let data = try JSONSerialization.data(withJSONObject: ["lines": lines], options: [.sortedKeys])
    FileHandle.standardOutput.write(data)
} catch {
    // Deliberately omit document text, paths, and framework diagnostics.
    let failure = error as NSError
    FileHandle.standardError.write(Data("Local OCR failed (\(failure.domain), code \(failure.code)).\n".utf8))
    exit(1)
}
