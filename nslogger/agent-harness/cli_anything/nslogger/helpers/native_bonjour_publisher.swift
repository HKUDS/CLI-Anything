import Darwin
import Foundation

final class PublisherDelegate: NSObject, NetServiceDelegate {
    func netServiceDidPublish(_ sender: NetService) {
        print("published type=\(sender.type) name=\(sender.name) port=\(sender.port)")
        fflush(stdout)
    }

    func netService(_ sender: NetService, didNotPublish errorDict: [String: NSNumber]) {
        print("publish-failed type=\(sender.type) name=\(sender.name) error=\(errorDict)")
        fflush(stdout)
    }

    func netServiceWillPublish(_ sender: NetService) {
        print("publishing type=\(sender.type) name=\(sender.name) port=\(sender.port)")
        fflush(stdout)
    }

    func netServiceDidStop(_ sender: NetService) {
        print("stopped type=\(sender.type) name=\(sender.name)")
        fflush(stdout)
    }
}

struct Arguments {
    var name = ""
    var port: Int32 = 50000
    var types: [String] = []
    var txt: [String: Data] = [:]
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
        case "--types":
            index += 1
            if index < args.count {
                parsed.types = args[index]
                    .split(separator: ",")
                    .map { normalizeServiceType(String($0)) }
                    .filter { !$0.isEmpty }
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
        default:
            break
        }
        index += 1
    }
    return parsed
}

func normalizeServiceType(_ type: String) -> String {
    if type.isEmpty {
        return type
    }
    return type.hasSuffix(".") ? type : "\(type)."
}

signal(SIGTERM) { _ in
    exit(0)
}
signal(SIGINT) { _ in
    exit(0)
}

setvbuf(stdout, nil, _IONBF, 0)

let arguments = parseArguments(CommandLine.arguments)
let delegate = PublisherDelegate()
var services: [NetService] = []

for type in arguments.types {
    let service = NetService(domain: "", type: type, name: arguments.name, port: arguments.port)
    service.includesPeerToPeer = true
    service.delegate = delegate
    if !arguments.txt.isEmpty {
        service.setTXTRecord(NetService.data(fromTXTRecord: arguments.txt))
    }
    service.publish()
    services.append(service)
}

if services.isEmpty {
    print("publish-failed error=no-service-types")
    exit(2)
}

RunLoop.main.run()
