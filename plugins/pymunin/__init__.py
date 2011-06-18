"""Foundations for creating MultiGraph Munin Plugins.

    - Munin Plugins can be created by subclassing the MuninPlugin Class.
    - Each plugin contains one or more graphs implemented by MuninGraph instances.
    - The muninMain function implements the entry point for Munin Plugins.

"""

import os.path
import sys
import re
import cPickle as pickle

__author__ = "Ali Onur Uyar"
__copyright__ = "Copyright 2011, Ali Onur Uyar"
__credits__ = ["Samuel Stauffer"]
__license__ = "GPL"
__version__ = "0.9"
__maintainer__ = "Ali Onur Uyar"
__email__ = "aouyar at gmail.com"
__status__ = "Development"


class MuninAttrFilter:
    """Class for implementing Attribute Filters for Munin Graphs.
    
    - Attributes are filtered using an Include List and an Exclude List.
    - If the include List is empty, all Attributes are enabled by default.
    - If the Include List is not empty, only the Attributes that are in the
      list are enabled.
    - Any Attribute that is in the Exclude List is disabled.
    
    """
    
    def __init__(self, list_include = [], list_exclude = [], attr_regex = None):
        """Initialize Munin Attribute Filter.
        
        @param list_include: Include List (List of attributes that are enabled.)
        @param list_exclude: Exclude List (List of attributes that are disabled.)
        @param attr_regex:  If the regex is defined, the Attributes in the 
                            Include List and Exclude List are ignored unless 
                            they comply with the format dictated by the match 
                            regex.
        
        """
        self._attrs = {}
        self._default = True
        if attr_regex:
            self._regex = re.compile(attr_regex)
        else:
            self._regex = None
        if list_include:
            self._default = False
            for attr in list_include:
                if not self._regex or self._regex.match(attr):
                    self._attrs[attr] = True
        if list_exclude:
            for attr in list_exclude:
                if not self._regex or self._regex.match(attr):
                    self._attrs[attr] = False
    
    def check(self, attr):
        return self._attrs.get(attr, self._default)


class MuninPlugin:
    """Base class for Munin Plugins

    Munin Plugins are implemented as child classes which contain
    single or multiple MuninGraph objects.

    """

    plugin_name = None
    """The name of the plugin executable.
    Must be overriden in child classes to indicate plugin name.
    If it ends with an underscore the name will be parsed to separate plugin
    argument embedded in the name."""

    isMultigraph = False
    """True for Multi-Graph Plugins, and False for Simple Plugins.
    Must be overriden in child classes to indicate plugin type."""

    def __init__(self, argv = (), env = {}):
        """Constructor for MuninPlugin Class.
        
        @param argv: List of command line arguments.
        @param env:  Dict of environment variables.
            
        """
        self._graphDict = {}
        self._graphNames = []
        self._subGraphDict = {}
        self.nestedGraphs = True
        self._filters = {}
        self._argv = argv
        self._env = env
        self.arg0 = None
        if (self.plugin_name is not None and argv is not None and len(argv) > 0 
            and re.search('_$', self.plugin_name)):
            mobj = re.match("%s(\S+)$" % self.plugin_name, argv[0])
            if mobj:
                self.arg0 = mobj.group(1)
        self._parseEnv()
        self.registerFilter('graphs', '[\w\-]+$')
                
    def _parseEnv(self,  env=None):
        """Utility method that parses through environment variables.
        
        Parses for environment variables common to all Munin Plugins:
            - MUNIN_STATEFILE
            - nested_graphs
        
        @param env: Dictionary of environment variables.
                    (Only used for testing. initialized automatically by constructor.
        
        """
        if not env:
            env = self._env
        if env.has_key('MUNIN_STATEFILE'):
            self._stateFile = env.get('MUNIN_STATEFILE')
        else:
            self._stateFile = '/tmp/munin-state-%s' % self.plugin_name
        if env.has_key('nested_graphs'):
            if re.match('/s*(no|off)/s*$',  env.get('nested_graphs'), 
                        re.IGNORECASE):
                self.nestedGraphs = False
       
    def registerFilter(self, filter_name, attr_regex = '\w+$'):
        """Register filter for including, excluding attributes in graphs through 
        the use of include_<name> and exclude_<name> environment variables. 
        Parse the environment variables to initialize filter.
        
        @param filter_name: Name of filter.
                            (Also determines suffix for environment variable name.)
        @param attr_regex: Regular expression string for checking valid items.
        
        """
        attrs = {}
        for prefix in ('include', 'exclude'):
            key = "%s_%s" % (prefix, filter_name)
            val = self._env.get(key)
            if val:
                attrs[prefix] = val.split(',')
            else:
                attrs[prefix] = []
        self._filters[filter_name] = MuninAttrFilter(attrs['include'], 
                                                     attrs['exclude'], 
                                                     attr_regex)
        
    def checkFilter(self, filter_name, attr):
        """Check if a specific graph attribute is enabled or disabled through 
        the use of a filter based on include_<name> and exclude_<name> 
        environment variables.
        
        @param filter_name: Name of the Filter.
        @param attr:        Name of the Attribute.
        
        @return:            Return True if the attribute is enabled.
        
        """
        filter = self._filters.get(filter_name)
        if filter:
            return filter.check(attr) 
        else:
            raise AttributeError("Undefined filter: %s" % filter_name)
                
    def graphEnabled(self, name):
        """Utility method to check if graph with the given name is enabled.
        
        @param name: Name of Root Graph Instance.
        @return:     Returns True if Root Graph is enabled, False otherwise.
            
        """
        return self.checkFilter('graphs', name)
        
    def saveState(self,  stateObj):
        """Utility methos to save plugin state stored in stateObj to persistent 
        storage to permit access to previous state in subsequent plugin runs.
        
        Any object that can be pickled and unpickled can be used to store the 
        plugin state.
        
        @param stateObj: Object that stores plugin state.
        
        """
        fp = open(self._stateFile,  'w')
        pickle.dump(stateObj, fp)
        try:
            pass
        except:
            raise Exception("Failure in storing plugin state in file: %s" 
                            % self._stateFile)
        return True
    
    def restoreState(self):
        """Utility method to restore plugin state from persistent storage to 
        permit access to previous plugin state.
        
        @return: Object that stores plugin state.
        
        """
        if os.path.exists(self._stateFile):
            try:
                fp = open(self._stateFile,  'r')
                stateObj = pickle.load(fp)
            except:
                raise Exception("Failure in reading plugin state from file: %s" 
                                % self._stateFile)
            return stateObj
        return None
        
    def appendGraph(self, name, graph):
        """Utility method to associate Graph Object to Plugin.
        
        This utility method is for use in constructor of child classes for
        associating a MuninGraph instances to the plugin.
        
        @param name:  Graph Name
        @param graph: MuninGraph Instance

        """
        self._graphDict[name] = graph
        self._graphNames.append(name)
        if not self.isMultigraph  and len(self._graphNames) > 1:
            raise AttributeError("Simple Munin Plugins cannot have more than one graph.")
        
    def appendSubgraph(self, parent_name,  graph_name, graph):
        """Utility method to associate Subgraph Instance to Root Graph Instance.

        This utility method is for use in constructor of child classes for 
        associating a MuninGraph Subgraph instance with a Root Graph instance.
        
        @param parent_name: Root Graph Name
        @param graph_name:  Subgraph Name
        @param graph:       MuninGraph Instance

        """
        if not self.isMultigraph:
            raise AttributeError("Simple Munin Plugins cannot have more than one graph.")
        if self._graphDict.has_key(parent_name):
            if not self._subGraphDict.has_key(parent_name):
                self._subGraphDict['parent_name'] = {}
            self._subGraphDict['parent_name']['graph_name'] = graph
        else:
            raise Exception("Invalid parent graph name %s used for subgraph %s."
                % (parent_name,  graph_name))
            
    def setGraphVal(self, graph_name, field_name, val):
        """Utility method to set Value for Field in Graph.
        
        The private method is for use in retrieveVals() method of child classes.
        
        @param name:    Graph Name
        @param valDict: Dictionary of monitored values

        """
        graph = self._graphDict.get(graph_name)
        if graph is not None:
            graph.setVal(field_name, val)
        else:
            raise Exception("Invalid graph name %s used for setting value." 
                            % graph_name)
    
    def setSubgraphVal(self,  parent_name,  graph_name,  val):
        """Set Value for Field in Subgraph.

        The private method is for use in retrieveVals() method of child
        classes.
        
        @param parent_name: Root Graph Name
        @param name:        Subgraph Name
        @param valDict:     Dictionary of monitored values

        """        
        graph = self._graphDict.get(parent_name)
        if graph is not None:
            graph.setVal("%s.%s" % (parent_name, graph_name),  val)
        else:
            raise Exception("Invalid parent graph name %s used "
                            "for setting value for subgraph %s."
                            % (parent_name, graph_name))
    
    def hasGraph(self, name):
        """Return true if graph with name is registered to plugin.
        
        @return: Boolean
        
        """
        return self._graphDict.has_key(name)
            
    def getGraphList(self):
        """Returns list of names of graphs registered to plugin.
        
        @return - List of graph names.
        
        """
        return self._graphNames

    def graphHasField(self, graph_name, field_name):
        """Return true if graph with name graph_name has field with 
        name field_name.
        
        @return: Boolean
        
        """
        return self._graphDict[graph_name].hasField(field_name)
            
    def getGraphFieldList(self, graph_name):
        """Returns list of names of fields for graph with name graph_name.
        
        @return - List of field names for graph.
        
        """
        return self._graphDict[graph_name].getFieldList()
        
    def retrieveVals(self):
        """Initialize measured values for Graphs.

        This method must be overwritten in child classes for initializing the
        values to be graphed by the Munin Plugin.

        """
        pass

    def autoconf(self):
        """Implements Munin Plugin Auto-Configuration Option.

        Auto-configuration is disabled by default. To implement 
        auto-configuration for the Munin Plugin, this method must be overwritten 
        in child class.

        """
        return False

    def config(self):
        """Implements Munin Plugin Graph Configuration.
        
        Prints out configuration for graphs.

        Use as is. Not required to be overwritten in child classes. The plugin
        will work correctly as long as the Munin Graph objects have been 
        populated.

        """
        for name in self._graphNames:
            graph = self._graphDict[name]
            if self.isMultigraph:
                print "multigraph %s" % name
            print graph.getConfig()
            print
        if self.nestedGraphs and self._subGraphDict:
            for (parent_name, subgraphs) in self._subGraphDict.iteritems():
                for (graph_name,  graph) in subgraphs:
                    print "multigraph %s.%s" % (parent_name,  graph_name)
                    print graph.getConfig()
                    print
        return True

    def suggest(self):
        """Implements Munin Plugin Suggest Option.

        Suggest option is disabled by default. To implement the Suggest option
        for the Munin, Plugin this method must be overwritten in child class.

        """
        return True

    def fetch(self):
        """Implements Munin Plugin Fetch Option.

        Prints out measured values.

        """
        self.retrieveVals()
        for name in self._graphNames:
            graph = self._graphDict[name]
            if self.isMultigraph:
                print "multigraph %s" % name
            print graph.getVals()
            print
        if self.nestedGraphs and self._subGraphDict:
            for (parent_name, subgraphs) in self._subGraphDict.iteritems():
                for (graph_name,  graph) in subgraphs:
                    print "multigraph %s.%s" % (parent_name,  graph_name)
                    print graph.getVals()
                    print
        return True

    def run(self):
        """Implements main entry point for plugin execution."""
        if len(self._argv) > 1 and len(self._argv[1]) > 0:
            oper = self._argv[1]
        else:
            oper = 'fetch'
        if oper == 'fetch':
            ret = self.fetch()
        elif oper == 'config':
            ret = self.config()
        elif oper == 'autoconf':
            ret = self.autoconf()
            if ret:
                print "yes"
            else:
                print "no"
            ret = True
        elif oper == 'suggest':
            ret = self.suggest()
        else:
            raise Exception("Invalid command argument: %s" % oper)
        return ret


class MuninGraph:
    """Base class for Munin Graphs

    """

    def __init__(self, title, category = None, vlabel=None, info=None, 
                 args =None, period=None, scale=None,  total=None, order=None, 
                 printfformat=None, witdh=None, height=None):
        """Initialize Munin Graph.
        
        @param title:        Graph Title
        @param category:     Graph Category
        @param vlabel:       Label on Vertical Axis
        @param info:         Graph Information
        @param args:         Args passed to RRDtool
        @param period:       Time Unit - 'second' / 'minute' (Default: 'second')
        @param scale:        Graph Scaling - True / False (Default: True)
        @param total:        Add a total field with sum of all datasources if 
                             defined. The value of the parameter is used as the 
                             label for the total field.
        @param order:        The order in which the fields are drawn on graph.
                             The attribute must contain a comma separated list 
                             of field names.
                             When the parameter is not used, the datasources are 
                             drawn in the order they are defined by default.
        @param printfformat: Format for printing numbers on graph. The defaults 
                             are usually OK and this parameter is rarely needed.
        @param width:        Graph width in pixels.
        @param height:       Graph height in pixels.
            .
        """
        self._graphAttrDict = locals()
        self._fieldNameList = []
        self._fieldAttrDict = {}
        self._fieldValDict = {}

    def addField(self, name, label, type=None,  draw=None, info=None, 
                 extinfo=None, colour=None, negative=None, graph=None, 
                 min=None, max=None, cdef=None, line=None, 
                 warning=None, critical=None):
        """Add field to Munin Graph
        
            @param name:     Field Name
            @param label:    Field Label
            @param type:     Stat Type:
                             'COUNTER' / 'ABSOLUTE' / 'DERIVE' / 'GAUGE'
            @param draw:     Graph Type:
                             'AREA' / 'LINE{1,2,3}' / 
                             'STACK' / 'LINESTACK{1,2,3}' / 'AREASTACK'
            @param info:     Detailed Field Info
            @param extinfo:  Extended Field Info
            @param colour:   Field Colour
            @param negative: Mirror Value
            @param graph:    Draw on Graph - True / False (Default: True)
            @param min:      Minimum Valid Value
            @param max:      Maximum Valid Value
            @param cdef:     CDEF
            @param line:     Adds horizontal line at value defined for field. 
            @param warning:  Warning Value
            @param critical: Critical Value
            
        """
        attrs = locals()
        self._fieldNameList.append(name)
        self._fieldAttrDict[name] = attrs

    def hasField(self, field_name):
        """Returns true if field with field_name exists.
        
        @return: Boolean
        
        """
        return self._fieldAttrDict.has_key(field_name)
    
    def getFieldList(self):
        """Returns list of field names registered to Munin Graph.
        
        @return: List of field names registered to Munin Graph.
        
        """
        return self._fieldNameList
    
    def getConfig(self):
        """Returns config entries for Munin Graph.
        
        @return: Multi-line text output with Munin Graph configuration. 
        
        """
        conf = []
        
        # Process Graph Attributes
        for key in ('title', 'category', 'vlabel', 'info', 'args', 'period', 
                    'scale', 'total', 'order', 'printfformat', 'width', 'height'):
            val = self._graphAttrDict.get(key)
            if val is not None:
                if isinstance(val, bool):
                    if val:
                        val = "yes"
                    else:
                        val = "no"
                conf.append("graph_%s %s" % (key,val))

        # Process Field Attributes
        for field_name in self._fieldNameList:
            field_attrs = self._fieldAttrDict.get(field_name)
            for key in ('label', 'type', 'draw', 'info', 'extinfo', 'colour',
                        'negative', 'graph', 'min', 'max', 'cdef', 
                        'line', 'warning', 'critical'):
                val = field_attrs.get(key)
                if val is not None:
                    if isinstance(val, bool):
                        if val:
                            val = "yes"
                        else:
                            val = "no"
                    conf.append("%s.%s %s" % (field_name, key, val))
        return "\n".join(conf)

    def setVal(self, name, val):
        """Set value for field in graph.
        
        @param name   : Graph Name
        @param value  : Value for field. 
        
        """
        self._fieldValDict[name] = val

    def getVals(self):
        """Returns value entries for Munin Graph
        
        @return: Multi-line text output with Munin Graph values.
        
        """
        vals = []
        for field_name in self._fieldNameList:
            val = self._fieldValDict.get(field_name)
            if val is not None:
                if isinstance(val, float):
                    vals.append("%s.value %f" % (field_name, val))
                else:
                    vals.append("%s.value %s" % (field_name, val))
        return "\n".join(vals)


def muninMain(pluginClass, argv = None, env = None):
    """Main Block for Munin Plugins.
    
    @param pluginClass: Child class of MuninPlugin that implements plugin.
    @param argv: List of command line arguments to Munin Plugin.
    @param env: Dictionary of environment variables passed to Munin Plugin.
    
    """
    if argv is None:
        argv = sys.argv
    if env is None:
        env = os.environ
    plugin = pluginClass(argv, env)
    ret = plugin.run()
    if ret:
        return 0
    else:
        return 1