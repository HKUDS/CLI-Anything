// Headless post-script for cli-anything-ghidra.
// Args: <command> <output json path> [argument]
// Commands: info [entry], functions|strings|imports [options file], decompile <name|addr>, xrefs <name|addr>
// Results are written as JSON to the output path; stdout is Ghidra log noise and is never parsed.

import java.io.File;
import java.io.Reader;
import java.util.Properties;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.StringDataInstance;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.symbol.ExternalLocation;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.Symbol;

public class CliAnythingQuery extends GhidraScript {

    @Override
    protected void run() throws Exception {
        String[] a = getScriptArgs();
        if (a.length < 2) {
            throw new IllegalArgumentException("usage: <command> <output> [argument]");
        }
        String command = a[0];
        String arg = a.length > 2 ? a[2] : "";
        int seconds = a.length > 3 ? Integer.parseInt(a[3]) : 60;  // decompiler budget, set by the CLI
        String json;
        switch (command) {
            case "info": json = info(arg); break;
            case "functions": json = functions(options(arg)); break;
            case "decompile": json = decompile(arg, seconds); break;
            case "strings": json = strings(options(arg)); break;
            case "imports": json = imports(options(arg)); break;
            case "xrefs": json = xrefs(arg); break;
            default: throw new IllegalArgumentException("unknown command: " + command);
        }
        Files.write(new File(a[1]).toPath(), json.getBytes(StandardCharsets.UTF_8));
    }

    // filter/limit/min come in a properties file (never on the command line, where cmd.exe would parse them)
    private Properties options(String path) throws Exception {
        Properties p = new Properties();
        if (!path.isEmpty()) {
            try (Reader r = Files.newBufferedReader(new File(path).toPath(), StandardCharsets.UTF_8)) {
                p.load(r);
            }
        }
        return p;
    }

    private static int number(Properties p, String key, int fallback) {
        String v = p.getProperty(key, "");
        return v.isEmpty() ? fallback : Integer.parseInt(v);
    }

    private String info(String entry) throws Exception {
        if (!entry.isEmpty()) {
            Address at = toAddr(entry);
            disassemble(at);
            if (createFunction(at, null) == null) {
                throw new IllegalStateException("could not create a function at " + entry);
            }
        }
        return "{\"format\":" + q(currentProgram.getExecutableFormat())
            + ",\"language\":" + q(currentProgram.getLanguageID().toString())
            + ",\"compiler\":" + q(currentProgram.getCompilerSpec().getCompilerSpecID().toString())
            + ",\"image_base\":" + q(currentProgram.getImageBase().toString())
            + ",\"functions\":" + countFunctions()
            + ",\"symbols\":" + currentProgram.getSymbolTable().getNumSymbols() + "}";
    }

    private int countFunctions() {
        int n = 0;
        FunctionIterator it = currentProgram.getListing().getFunctions(true);
        while (it.hasNext()) {
            it.next();
            n++;
        }
        return n;
    }

    private String functions(Properties o) {
        String filter = o.getProperty("filter", "").toLowerCase();
        int limit = number(o, "limit", 0);
        StringBuilder out = new StringBuilder("[");
        int n = 0;
        FunctionIterator it = currentProgram.getListing().getFunctions(true);
        while (it.hasNext() && (limit == 0 || n < limit)) {
            Function f = it.next();
            if (!filter.isEmpty() && !f.getName().toLowerCase().contains(filter)) {
                continue;
            }
            out.append(n++ == 0 ? "" : ",").append("{\"name\":").append(q(f.getName()))
                .append(",\"address\":").append(q(f.getEntryPoint().toString()))
                .append(",\"size\":").append(f.getBody().getNumAddresses()).append("}");
        }
        return out.append("]").toString();
    }

    private Function findFunction(String target) {
        List<Function> byName = getGlobalFunctions(target);
        if (byName != null && !byName.isEmpty()) {
            return byName.get(0);
        }
        for (Symbol s : currentProgram.getSymbolTable().getSymbols(target)) {  // namespaced names, for example C++ methods
            Function f = getFunctionAt(s.getAddress());
            if (f != null) {
                return f;
            }
        }
        Address at = toAddr(target);
        return at == null ? null : getFunctionContaining(at);
    }

    private String decompile(String target, int seconds) throws Exception {
        Function f = findFunction(target);
        if (f == null) {
            throw new IllegalArgumentException("no function named or containing " + target);
        }
        DecompInterface decompiler = new DecompInterface();
        try {
            DecompileOptions options = new DecompileOptions();
            options.grabFromProgram(currentProgram);
            options.setMaxPayloadMBytes(2047);  // the default 50 MB fails on huge functions ("Response buffer size exceeded")
            decompiler.setOptions(options);
            decompiler.openProgram(currentProgram);
            DecompileResults r = decompiler.decompileFunction(f, seconds, monitor);
            if (!r.decompileCompleted()) {
                throw new IllegalStateException("decompile failed: " + r.getErrorMessage());
            }
            return "{\"name\":" + q(f.getName()) + ",\"address\":" + q(f.getEntryPoint().toString())
                + ",\"c\":" + q(r.getDecompiledFunction().getC()) + "}";
        } finally {
            decompiler.dispose();
        }
    }

    private String strings(Properties o) {
        int minLength = number(o, "min", 1);
        int limit = number(o, "limit", 0);
        StringBuilder out = new StringBuilder("[");
        int n = 0;
        for (Data d : currentProgram.getListing().getDefinedData(true)) {
            if (limit != 0 && n >= limit) {
                break;
            }
            StringDataInstance s = StringDataInstance.getStringDataInstance(d);
            if (s != null && s != StringDataInstance.NULL_INSTANCE) {
                String value = s.getStringValue();
                if (value == null || value.length() < minLength) {  // null: a string in uninitialized memory
                    continue;
                }
                out.append(n++ == 0 ? "" : ",").append("{\"address\":").append(q(d.getAddress().toString()))
                    .append(",\"length\":").append(value.length()).append(",\"value\":").append(q(value)).append("}");
            }
        }
        return out.append("]").toString();
    }

    private String imports(Properties o) {
        int limit = number(o, "limit", 0);
        StringBuilder out = new StringBuilder("[");
        int n = 0;
        for (String lib : currentProgram.getExternalManager().getExternalLibraryNames()) {
            var locations = currentProgram.getExternalManager().getExternalLocations(lib);
            while (locations.hasNext() && (limit == 0 || n < limit)) {
                ExternalLocation loc = locations.next();
                out.append(n++ == 0 ? "" : ",").append("{\"library\":").append(q(lib))
                    .append(",\"name\":").append(q(loc.getLabel())).append("}");
            }
        }
        return out.append("]").toString();
    }

    private String xrefs(String target) {
        Address at = null;
        List<Function> byName = getGlobalFunctions(target);
        if (byName != null && !byName.isEmpty()) {
            at = byName.get(0).getEntryPoint();
        } else {
            for (Symbol s : currentProgram.getSymbolTable().getSymbols(target)) {
                at = s.getAddress();
                break;
            }
            if (at == null) {
                at = toAddr(target);
            }
        }
        if (at == null) {
            throw new IllegalArgumentException("cannot resolve " + target);
        }
        List<String> items = new ArrayList<>();
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(at);  // lazy, unlike an array
        while (refs.hasNext()) {
            Reference r = refs.next();
            Function in = getFunctionContaining(r.getFromAddress());
            items.add("{\"from\":" + q(r.getFromAddress().toString()) + ",\"type\":" + q(r.getReferenceType().getName())
                + ",\"function\":" + (in == null ? "null" : q(in.getName())) + "}");
        }
        return "{\"target\":" + q(at.toString()) + ",\"truncated\":false"
            + ",\"references\":[" + String.join(",", items) + "]}";
    }

    private static String q(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        b.append(String.format("\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
            }
        }
        return b.append('"').toString();
    }
}
