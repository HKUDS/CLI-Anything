import Darwin
import Foundation
import Security

func emit(_ fields: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: fields, options: []),
       let line = String(data: data, encoding: .utf8) {
        print(line)
        fflush(stdout)
    }
}

struct Arguments {
    var name = ""
    var port: Int32 = 50000
    var type = "_nslogger-ssl._tcp."
    var txt: [String: Data] = [:]
    var secure = false
    var p12Path: String?
    var p12Password = ""
}

func normalizeServiceType(_ type: String) -> String {
    if type.isEmpty {
        return type
    }
    return type.hasSuffix(".") ? type : "\(type)."
}

func parseArguments(_ args: [String]) -> Arguments {
    var parsed = Arguments()
    var index = 1
    while index < args.count {
        let arg = args[index]
        switch arg {
        case "--name":
            index += 1
            if index < args.count {
                parsed.name = args[index]
            }
        case "--port":
            index += 1
            if index < args.count, let port = Int32(args[index]) {
                parsed.port = port
            }
        case "--type":
            index += 1
            if index < args.count {
                parsed.type = normalizeServiceType(args[index])
            }
        case "--txt":
            index += 1
            if index < args.count {
                let parts = args[index].split(separator: "=", maxSplits: 1).map(String.init)
                let key = parts.first ?? ""
                let value = parts.count > 1 ? parts[1] : ""
                if !key.isEmpty {
                    parsed.txt[key] = value.data(using: .utf8) ?? Data()
                }
            }
        case "--secure":
            parsed.secure = true
        case "--p12":
            index += 1
            if index < args.count {
                parsed.p12Path = args[index]
            }
        case "--p12-pass":
            index += 1
            if index < args.count {
                parsed.p12Password = args[index]
            }
        default:
            break
        }
        index += 1
    }
    return parsed
}

func loadIdentity(path: String?, password: String) -> SecIdentity? {
    guard let path else {
        return nil
    }
    guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else {
        emit(["event": "error", "message": "failed to read pkcs12 identity"])
        return nil
    }
    let options = [kSecImportExportPassphrase as String: password]
    var items: CFArray?
    let status = SecPKCS12Import(data as CFData, options as CFDictionary, &items)
    guard status == errSecSuccess,
          let imported = items as? [[String: Any]],
          let identityValue = imported.first?[kSecImportItemIdentity as String] else {
        emit(["event": "error", "message": "failed to import pkcs12 identity", "status": Int(status)])
        return nil
    }
    return (identityValue as! SecIdentity)
}

final class Connection: NSObject, StreamDelegate {
    private let input: InputStream
    private let output: OutputStream
    private let secure: Bool
    private let identity: SecIdentity?
    private var buffer = Data()
    private var connected = false

    init(input: InputStream, output: OutputStream, secure: Bool, identity: SecIdentity?) {
        self.input = input
        self.output = output
        self.secure = secure
        self.identity = identity
    }

    func open() {
        if secure {
            guard let identity else {
                emit(["event": "error", "message": "missing ssl identity"])
                return
            }
            let settings: [String: Any] = [
                kCFStreamSSLLevel as String: kCFStreamSocketSecurityLevelNegotiatedSSL,
                kCFStreamSSLValidatesCertificateChain as String: false,
                kCFStreamSSLIsServer as String: true,
                kCFStreamSSLCertificates as String: [identity],
            ]
            input.setProperty(settings, forKey: Stream.PropertyKey(rawValue: kCFStreamPropertySSLSettings as String))
        }

        input.delegate = self
        output.delegate = self
        input.schedule(in: .current, forMode: .default)
        output.schedule(in: .current, forMode: .default)
        input.open()
        output.open()
    }

    func close() {
        input.close()
        output.close()
        input.remove(from: .current, forMode: .default)
        output.remove(from: .current, forMode: .default)
    }

    func stream(_ aStream: Stream, handle eventCode: Stream.Event) {
        switch eventCode {
        case .openCompleted:
            if !connected {
                connected = true
                emit(["event": "connect"])
            }
        case .hasBytesAvailable:
            readAvailableBytes()
        case .endEncountered:
            emit(["event": "disconnect"])
            close()
        case .errorOccurred:
            let message = aStream.streamError?.localizedDescription ?? "stream error"
            emit(["event": "error", "message": message])
            close()
        default:
            break
        }
    }

    private func readAvailableBytes() {
        var chunk = [UInt8](repeating: 0, count: 64 * 1024)
        while input.hasBytesAvailable {
            let count = input.read(&chunk, maxLength: chunk.count)
            if count <= 0 {
                break
            }
            buffer.append(chunk, count: count)
            processFrames()
        }
    }

    private func processFrames() {
        while buffer.count >= 4 {
            let headerStart = buffer.startIndex
            let headerEnd = buffer.index(headerStart, offsetBy: 4)
            let length = buffer[headerStart..<headerEnd].reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }
            let frameLength = Int(length)
            if frameLength == 0 {
                buffer.removeSubrange(headerStart..<headerEnd)
                continue
            }
            if buffer.count < 4 + frameLength {
                return
            }
            let frameEnd = buffer.index(headerEnd, offsetBy: frameLength)
            let frame = buffer.subdata(in: headerEnd..<frameEnd)
            buffer.removeSubrange(headerStart..<frameEnd)
            emit(["event": "frame", "payload": frame.base64EncodedString()])
        }
    }
}

final class ListenerDelegate: NSObject, NetServiceDelegate {
    private let secure: Bool
    private let identity: SecIdentity?
    private var connections: [Connection] = []

    init(secure: Bool, identity: SecIdentity?) {
        self.secure = secure
        self.identity = identity
    }

    func netServiceWillPublish(_ sender: NetService) {
        emit(["event": "debug", "message": "publishing type=\(sender.type) name=\(sender.name) port=\(sender.port)"])
    }

    func netServiceDidPublish(_ sender: NetService) {
        emit(["event": "ready", "name": sender.name, "port": sender.port, "type": sender.type])
    }

    func netService(_ sender: NetService, didNotPublish errorDict: [String: NSNumber]) {
        emit(["event": "error", "message": "publish failed", "error": errorDict.description])
    }

    func netService(_ sender: NetService, didAcceptConnectionWith inputStream: InputStream, outputStream: OutputStream) {
        emit(["event": "debug", "message": "accepted native NetService connection"])
        let connection = Connection(input: inputStream, output: outputStream, secure: secure, identity: identity)
        connections.append(connection)
        connection.open()
    }
}

signal(SIGTERM) { _ in
    exit(0)
}
signal(SIGINT) { _ in
    exit(0)
}
// Ignore SIGPIPE so a broken stdout pipe doesn't kill the process
signal(SIGPIPE, SIG_IGN)

setvbuf(stdout, nil, _IONBF, 0)

let arguments = parseArguments(CommandLine.arguments)
let identity = arguments.secure ? loadIdentity(path: arguments.p12Path, password: arguments.p12Password) : nil
if arguments.secure && identity == nil {
    exit(3)
}

let delegate = ListenerDelegate(secure: arguments.secure, identity: identity)
let service = NetService(domain: "", type: arguments.type, name: arguments.name, port: arguments.port)
service.includesPeerToPeer = true
service.delegate = delegate
if !arguments.txt.isEmpty {
    service.setTXTRecord(NetService.data(fromTXTRecord: arguments.txt))
}
service.publish(options: .listenForConnections)

// A repeating Timer keeps the RunLoop alive in .default mode even after all
// NSStream sources are removed (e.g., after the iOS app disconnects).
// Without a source, RunLoop.main.run()'s internal run(mode:before:) returns
// false immediately and the process exits.
// Port() is NOT used because NSMessagePort relies on Mach bootstrap, which
// is unavailable in a new-session subprocess (start_new_session=True) and
// causes SIGTRAP at runtime.
// The timer closure captures delegate and service strongly, ensuring ARC
// keeps them alive for the lifetime of the RunLoop regardless of optimizer.
let _keepAliveRefs: [AnyObject] = [delegate, service]
Timer.scheduledTimer(withTimeInterval: 1e8, repeats: true) { _ in
    _ = _keepAliveRefs
}

RunLoop.main.run()
