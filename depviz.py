#!/usr/bin/env python
"""
The MIT License (MIT)

Copyright (c) 2013 Andrew Wooster

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
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

def dependencies_for_resolved_framework_path(lib_base, framework_path, dependencies, dep_to_visibility, exclude_dylibs=True):
    def visibility_from_path(path):
        visibility = DEPENDENCY_UNKNOWN
        if '/PrivateFrameworks/' in path:
            visibility = DEPENDENCY_PRIVATE
        elif '/Frameworks/' in path:
            visibility = DEPENDENCY_PUBLIC
        return visibility
    
    real_framework_path = framework_path
    if not framework_path.startswith(lib_base):
        real_framework_path = lib_base + framework_path
        if not os.path.exists(real_framework_path):
            real_framework_path = framework_path
    if not os.path.exists(real_framework_path):
        print >> sys.stderr, "Unable to find framework:", real_framework_path
        return
    
    (path, filename) = os.path.split(real_framework_path)
    (base, ext) = os.path.splitext(filename)
    (status, output) = run_command("otool -L %s" % escape_arg(real_framework_path))
    lines = output.splitlines()
    
    dep_to_visibility[base] = visibility_from_path(real_framework_path)
    
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
        visibility = visibility_from_path(f_path)
        if exclude_dylibs and f_path.endswith("dylib"):
            continue
        
        should_recurse = (dep_to_visibility.get(depname) is None)
        dep_to_visibility[depname] = visibility
        dependencies.setdefault(base, [])
        if not depname in dependencies[base]:
            dependencies[base].append(depname)
        if should_recurse:
            dependencies_for_resolved_framework_path(lib_base, f_path, dependencies, dep_to_visibility, exclude_dylibs=exclude_dylibs)

def dependencies_for_framework_path(framework_path, dependencies, dep_to_visibility, exclude_dylibs=True):
    (path, filename) = os.path.split(framework_path)
    (base, ext) = os.path.splitext(filename)
    lib_path = os.path.join(framework_path, base)
    lib_parts = lib_path.split(os.sep)
    lib_base_parts = []
    for part in lib_parts:
        if part == "System":
            break
        lib_base_parts.append(part)
    lib_base = os.sep.join(lib_base_parts)
    return dependencies_for_resolved_framework_path(lib_base, lib_path, dependencies, dep_to_visibility, exclude_dylibs=exclude_dylibs)

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
            dependencies_for_framework_path(full_path, dependencies, dep_to_visibility)
    update_dependencies(dependencies, dep_to_visibility, library_path, "Frameworks")
    update_dependencies(dependencies, dep_to_visibility, library_path, "PrivateFrameworks")
    return (dependencies, dep_to_visibility)

def dot_for_dependencies(dependencies, dep_to_visibility, framework_depnames=None):
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
    
    
    if framework_depnames is None:
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
            l.append("\t%s [label=\"%s\", fillcolor=\"%s\"];" % (nodename, framework_name, color))
        for framework_name, deps in dependencies.iteritems():
            if nodes.get(framework_name) is None:
                print >> sys.stderr, "Unknown node", framework_name
                continue
            from_nodename = nodes[framework_name]
            if len(deps) == 0:
                l.append("\t\"%s\" -> {};" % framework_name)
            for lib_name in deps:
                to_nodename = nodes[lib_name]
                l.append("\t%s -> %s; // %s -> %s" % (from_nodename, to_nodename, framework_name, lib_name))
    else:
        def gather_dependents(dependencies, framework_name, seen=None):
            """Get a list of all the frameworks wich depend on framework_name, recursively."""
            results = []
            if seen is None:
                seen = []
            for framework, deps in dependencies.iteritems():
                if framework_name in deps:
                    if framework in seen:
                        continue
                    seen.append(framework)
                    # framework depends on framework_name
                    results.append(framework_name)
                    for result in gather_dependents(dependencies, framework, seen=seen):
                        results.append(result)
            return list(set(results))
        frameworks_to_print = []
        for framework_depname in framework_depnames:
            for f in gather_dependents(dependencies, framework_depname):
                frameworks_to_print.append(f)
        frameworks_to_print = list(set(frameworks_to_print))
        nodes = {}
        seen_deps = []
        i = 0
        for framework_name, visibility in dep_to_visibility.iteritems():
            if framework_name in seen_deps:
                continue
            if framework_name not in frameworks_to_print:
                continue
            nodename = "Node%d" % i
            i += 1
            nodes[framework_name] = nodename
            seen_deps.append(framework_name)
            color = color_for_visibility(dep_to_visibility[framework_name])
            l.append("\t%s [label=\"%s\", style=filled, fillcolor=\"%s\"];" % (nodename, framework_name, color))
        for framework_name, deps in dependencies.iteritems():
            if framework_name in frameworks_to_print:
                if nodes.get(framework_name) is None:
                    print >> sys.stderr, "Unknown node", framework_name
                    continue
                from_nodename = nodes[framework_name]
                if len(deps) == 0:
                    l.append("\t\"%s\" -> {};" % framework_name)
                for lib_name in deps:
                    if lib_name in frameworks_to_print:
                        to_nodename = nodes[lib_name]
                        l.append("\t%s -> %s; // %s -> %s" % (from_nodename, to_nodename, framework_name, lib_name))
                
    l.append("}\n")
    return "\n".join(l)

def main(library_path, framework_depnames=None):
    library_path = os.path.expanduser(library_path)
    (dependencies, dep_to_visibility) = dependencies_for_system_library_path(library_path)
    dot_output = dot_for_dependencies(dependencies, dep_to_visibility, framework_depnames=framework_depnames)
    print >> sys.stdout, dot_output

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print >> sys.stderr, "Usage: %s [SDK System Library Path] [framework name ...]"
        print >> sys.stderr, "  Where the library path is like /System/Library"
        print >> sys.stderr, "  Where the framework name (optional) is one to determine what depends on it"
        sys.exit(1)
    framework_depnames = None
    if len(sys.argv) > 2:
        framework_depnames = sys.argv[2:]
    main(sys.argv[1], framework_depnames=framework_depnames)
