import asyncio
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from app.core.database import engine, Session
from app.models import Responsavel, Beneficiario, Auxilio
from typing import Optional


class ImportadorCSV:
    """Classe para importar dados de auxílios do CSV para o banco de dados."""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = None
        self.stats = {
            'responsaveis_novos': 0,
            'beneficiarios_novos': 0,
            'auxilios_novos': 0,
            'erros': 0
        }
    
    def carregar_csv(self):
        """Carrega o arquivo CSV."""
        print(f"Carregando arquivo CSV: {self.csv_path}")
        self.df = pd.read_csv(self.csv_path, dtype=str)
        
        self.df.columns = self.df.columns.str.strip()
        
        print(f"Total de registros no CSV: {len(self.df)}")
        print(f"Colunas encontradas: {list(self.df.columns)}")
        
        self.df = self.df.fillna('')
        
        return self
    
    async def buscar_ou_criar_responsavel(
        self, 
        session: AsyncSession, 
        nis: str, 
        cpf: str, 
        nome: str
    ) -> Responsavel:
        """Busca um responsável existente ou cria um novo."""
        
        # Buscar responsável existente
        result = await session.execute(
            select(Responsavel).where(Responsavel.nis_responsavel == nis)
        )
        responsavel = result.scalar_one_or_none()
        
        if responsavel:
            if cpf and not responsavel.cpf_responsavel:
                responsavel.cpf_responsavel = cpf
            if nome and not responsavel.nome_responsavel:
                responsavel.nome_responsavel = nome
        else:
            responsavel = Responsavel(
                nis_responsavel=nis,
                cpf_responsavel=cpf or None,
                nome_responsavel=nome or None
            )
            session.add(responsavel)
            self.stats['responsaveis_novos'] += 1
        
        return responsavel
    
    async def buscar_ou_criar_beneficiario(
        self,
        session: AsyncSession,
        row: pd.Series
    ) -> Optional[Beneficiario]:
        """Busca um beneficiário existente ou cria um novo."""
        
        nis_beneficiario = row.get('nis_beneficiario', '').strip()
        
        if not nis_beneficiario:
            return None
        
        # Buscar beneficiário existente
        result = await session.execute(
            select(Beneficiario).where(Beneficiario.nis_beneficiario == nis_beneficiario)
        )
        beneficiario = result.scalar_one_or_none()
        
        if beneficiario:
            # Atualizar dados se necessário (opcional)
            pass
        else:
            # Criar novo beneficiário
            beneficiario = Beneficiario(
                nis_beneficiario=nis_beneficiario,
                cpf_beneficiario=row.get('cpf_beneficiario', None) or None,
                nome_beneficiario=row.get('nome_beneficiario', None) or None,
                uf=row.get('uf', None) or None,
                codigo_ibge_municipio=int(row['codigo_ibge_municipio']) if row.get('codigo_ibge_municipio') and row['codigo_ibge_municipio'] != '' else None,
                municipio=row.get('municipio', None) or None,
                nis_responsavel=row.get('nis_responsavel', None) or None
            )
            session.add(beneficiario)
            self.stats['beneficiarios_novos'] += 1
        
        return beneficiario
    
    async def criar_auxilio(
        self,
        session: AsyncSession,
        row: pd.Series,
        nis_beneficiario: str
    ) -> Auxilio:
        """Cria um novo registro de auxílio."""
        
        auxilio = Auxilio(
            ano_mes=row.get('ano_mes', None) or None,
            enquadramento=row.get('enquadramento', None) or None,
            parcela=int(row['parcela']) if row.get('parcela') and row['parcela'] != '' else None,
            observacao=row.get('observacao', None) or None,
            valor=float(row['valor'].replace(',', '.')) if row.get('valor') and row['valor'] != '' else None,
            nis_beneficiario=nis_beneficiario
        )
        
        session.add(auxilio)
        self.stats['auxilios_novos'] += 1
        
        return auxilio
    
    async def processar_linha(self, session: AsyncSession, row: pd.Series):
        """Processa uma linha do CSV."""
        
        try:
            # 1. Processar Responsável (se existir)
            nis_responsavel = row.get('nis_responsavel', '').strip()
            if nis_responsavel:
                await self.buscar_ou_criar_responsavel(
                    session,
                    nis_responsavel,
                    row.get('cpf_responsavel', ''),
                    row.get('nome_responsavel', '')
                )
            
            # 2. Processar Beneficiário
            beneficiario = await self.buscar_ou_criar_beneficiario(session, row)
            
            if not beneficiario:
                print(f"Aviso: NIS do beneficiário não encontrado na linha")
                return
            
            # 3. Processar Auxílio
            await self.criar_auxilio(session, row, beneficiario.nis_beneficiario)
            
        except Exception as e:
            self.stats['erros'] += 1
            print(f"Erro ao processar linha: {e}")
            print(f"Dados da linha: {row.to_dict()}")
            raise
    
    async def importar(self, batch_size: int = 100):
        """Importa todos os dados do CSV para o banco."""
        
        if self.df is None:
            self.carregar_csv()
        
        print("\nIniciando importação...")
        
        total_linhas = len(self.df)
        
        async with Session() as session:
            for i in range(0, total_linhas, batch_size):
                batch = self.df.iloc[i:i + batch_size]
                
                print(f"Processando lote {i // batch_size + 1} ({i + 1}-{min(i + batch_size, total_linhas)} de {total_linhas})...")
                
                for _, row in batch.iterrows():
                    await self.processar_linha(session, row)
                
                # Commit em lotes
                await session.commit()
                print(f"Lote commitado com sucesso!")
        
        print("\n" + "="*50)
        print("IMPORTAÇÃO CONCLUÍDA!")
        print("="*50)
        print(f"Responsáveis novos criados: {self.stats['responsaveis_novos']}")
        print(f"Beneficiários novos criados: {self.stats['beneficiarios_novos']}")
        print(f"Auxílios novos criados: {self.stats['auxilios_novos']}")
        print(f"Erros encontrados: {self.stats['erros']}")
        print("="*50)


async def main():
    """Função principal para executar a importação."""
    
    # Configurar o caminho do arquivo CSV
    csv_path = "dados_auxilios.csv"  # ALTERE AQUI para o caminho do seu CSV
    
    importador = ImportadorCSV(csv_path)
    
    # Carregar CSV
    importador.carregar_csv()
    
    await importador.importar(batch_size=100)


if __name__ == "__main__":
    asyncio.run(main())