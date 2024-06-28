from core.models.config import ServiceConfig

from patch import yaml


def test_load_config():
    _config = """
    
    datasource:
      app: !module modules.datasource.app.DataSourceApp
      handlers:
        - modules.datasource.handler
        - modules.datasource.command._akshare
      protocol: 
        module: !module core.adapters.orm.SqlAlchemyProtocol
        unit_of_work:
          module: !module core.adapters.orm.SqlAlchemyAsyncUnitOfWork
          url: http://localhost:9090
          metadata: !module modules.datasource.orm.metadata
    """
    config = yaml.safe_load(_config)
    # config = ServiceConfig.model_construct(**config['datasource'])
    config = ServiceConfig(**config['datasource'])
