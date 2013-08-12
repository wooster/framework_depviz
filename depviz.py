#!/usr/bin/env python
import os
import subprocess
import sys

def escape_arg(argument):
    """Escapes an argument to a command line utility."""
    argument = argument.replace('\\', "\\\\").replace("'", "\'").replace('"', '\\"').replace("!", "\\!").replace("`", "\\`")
    return "\"%s\"" % argument

def run_command(command, verbose=False):
    """Runs the command and returns the status and the output."""
    if verbose:
        sys.stderr.write("Running: %s\n" % command)
    p = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    stdin, stdout = (p.stdin, p.stdout)
    output = stdout.read()
    output = output.strip("\n")
    status = stdin.close()
    stdout.close()
    p.wait()
    return (p.returncode, output)

DEPENDENCY_PRIVATE = 'Private'
DEPENDENCY_PUBLIC = 'Public'
DEPENDENCY_UNKNOWN = 'Unknown'

def dependencies_for_framework_path(framework_path, exclude_dylibs=True):
    (path, filename) = os.path.split(framework_path)
    (base, ext) = os.path.splitext(filename)
    lib_path = os.path.join(framework_path, base)
    (status, output) = run_command("otool -L %s" % escape_arg(lib_path))
    lines = output.splitlines()
    dependencies = []
    for line in lines:
        if not line.startswith("\t"):
            continue
        if not "(" in line:
            continue
        parts = line.split("(")
        if not len(parts) > 1:
            continue
        f_path = parts[0].strip()
        (_, depname) = os.path.split(f_path)
        if depname == base:
            # Exclude self-dependency.
            continue
        visibility = DEPENDENCY_UNKNOWN
        if exclude_dylibs and f_path.endswith("dylib"):
            continue
        if '/PrivateFrameworks/' in f_path:
            visibility = DEPENDENCY_PRIVATE
        elif '/Frameworks/' in f_path:
            visibility = DEPENDENCY_PUBLIC
        dependencies.append((depname, visibility))
    return (base, dependencies)

def dependencies_for_system_library_path(library_path):
    entries = os.listdir(library_path)
    if "/System/Library" not in library_path or "Frameworks" not in entries or "PrivateFrameworks" not in entries:
        print >> sys.stderr, "Path doesn't look like it points to the System/Library folder of an SDK."
        sys.exit(1)
    dependencies = {}
    dep_to_visibility = {}
    def update_dependencies(dependencies, dep_to_visibility, library_path, f_path):
        framework_paths = os.listdir(os.path.join(library_path, f_path))
        for framework_path in framework_paths:
            if not framework_path.endswith(".framework"):
                continue
            full_path = os.path.join(library_path, f_path, framework_path)
            (framework_name, framework_dependencies) = dependencies_for_framework_path(full_path)
            if "/PrivateFrameworks/" in framework_path:
                dep_to_visibility[framework_name] = DEPENDENCY_PRIVATE
            elif "/Frameworks/" in framework_path:
                dep_to_visibility[framework_name] = DEPENDENCY_PUBLIC
            dependencies.setdefault(framework_name, [])
            for dep in framework_dependencies:
                dependencies[framework_name].append(dep)
                (depname, visibility) = dep
                dep_to_visibility[depname] = visibility
    update_dependencies(dependencies, dep_to_visibility, library_path, "Frameworks")
    update_dependencies(dependencies, dep_to_visibility, library_path, "PrivateFrameworks")
    return (dependencies, dep_to_visibility)

def dot_for_dependencies(dependencies, dep_to_visibility):
    l = []
    l.append("digraph G {")
    l.append("\tnode [shape=box];")
    
    def color_for_visibility(visibility):
        if visibility == DEPENDENCY_PRIVATE:
            return "#FFD1E0"
        elif visibility == DEPENDENCY_PUBLIC:
            return "#D1FFD2"
        else:
            return "#FFFFFF"
    
    nodes = {}
    seen_deps = []
    i = 0
    for framework_name, visibility in dep_to_visibility.iteritems():
        if framework_name in seen_deps:
            continue
        nodename = "Node%d" % i
        i += 1
        nodes[framework_name] = nodename
        seen_deps.append(framework_name)
        color = color_for_visibility(dep_to_visibility[framework_name])
        l.append("%s [label=\"%s\", fillcolor=\"%s\"];" % (nodename, framework_name, color))
    print nodes
    #for framework_name, _ in dependencies.iteritems():
    #    if nodes.get(framework_name) is None:
    #        nodename = "Node%d" % i
    #        i += 1
    #        nodes[framework_name] = nodename
    #        seen_deps.append(framework_name)
    #        color = color_for_visibility(dep_to_visibility[framework_name])
    #        l.append("%s [label=\"%s\", fillcolor=\"%s\"];" % (nodename, framework_name, color))
    
    for framework_name, deps in dependencies.iteritems():
        if nodes.get(framework_name) is None:
            print >> sys.stderr, "Unknown node", framework_name
            continue
        from_nodename = nodes[framework_name]
        if len(deps) == 0:
            l.append("\t\"%s\" -> {};" % framework_name)
        for (lib_name, visibility) in deps:
            to_nodename = nodes[lib_name]
            l.append("\t%s -> %s;" % (from_nodename, to_nodename))
    l.append("}\n")
    return "\n".join(l)

def main(library_path):
    (dependencies, dep_to_visibility) = dependencies_for_system_library_path(library_path)
    dot_output = dot_for_dependencies(dependencies, dep_to_visibility)
    print >> sys.stdout, dot_output

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print >> sys.sterr, "Usage: %s [SDK System Library Path]"
        sys.exit(1)
    main(sys.argv[1])
