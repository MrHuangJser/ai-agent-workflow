from agentscope.agent import ReActAgent


class RequirementAgent(ReActAgent):
    """
    用于需求分析的专家 Agent。
    此类继承了 ReActAgent 的所有功能，其独特的行为由系统提示和所配备的工具定义。
    未来可以在此类中添加特定的钩子或方法以实现更复杂的逻辑。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
