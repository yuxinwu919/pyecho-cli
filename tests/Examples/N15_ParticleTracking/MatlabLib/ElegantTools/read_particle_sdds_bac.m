function [ L_ok,xpt,Charge,description,idx ] = read_particle_sdds(filename)
% function [ L_ok,xpt,Charge,{description,{idx}} ] = read_elegant_distribution(filename )
%   Detailed explanation goes here
%------------------------------------------------
% elegant phase space:
% x  meter
% xp unit  (x-prime)
% y  meter
% yp unit  (y-prime)
% t  sec
% p  unit  (normalized momentum gamma*beta)
%%
import SDDS.java.SDDS.*
sdds=sddsload(filename);
L_ok=true;
L_ok=and(L_ok,strcmp(sdds.filename,filename));
L_ok=and(L_ok,strcmp(sdds.description.contents,'output phase space'));
L_ok=and(L_ok,strcmp(sdds.column.x.type ,'double'));
L_ok=and(L_ok,strcmp(sdds.column.xp.type,'double'));
L_ok=and(L_ok,strcmp(sdds.column.y.type ,'double'));
L_ok=and(L_ok,strcmp(sdds.column.yp.type,'double'));
L_ok=and(L_ok,strcmp(sdds.column.t.type ,'double'));
L_ok=and(L_ok,strcmp(sdds.column.p.type ,'double'));
L_ok=and(L_ok,strcmp(sdds.column.x.units ,      'm'));
L_ok=and(L_ok,isempty(sdds.column.xp.units));
L_ok=and(L_ok,strcmp(sdds.column.y.units ,      'm'));
L_ok=and(L_ok,isempty(sdds.column.yp.units));
L_ok=and(L_ok,strcmp(sdds.column.t.units ,      's'));
L_ok=and(L_ok,strcmp(sdds.column.p.units ,'m$be$nc'));
L_ok=and(L_ok,strcmp(sdds.column.particleID.type,'long'));
L_ok=and(L_ok,isempty(sdds.parameter.Step.units));
L_ok=and(L_ok,strcmp(sdds.parameter.pCentral.units ,'m$be$nc'));
L_ok=and(L_ok,strcmp(sdds.parameter.Charge.units,'C'));
L_ok=and(L_ok,isempty(sdds.parameter.Particles.units));
%%
if L_ok
    if nargout>=4, description=char(sdds.description.text); end
    sdds.column.x.page1=SDDSUtil.castArrayAsDouble(sdds.column.x.page1,...
                        SDDSUtil.identifyType(sdds.column.x.type));
    sdds.column.xp.page1=SDDSUtil.castArrayAsDouble(sdds.column.xp.page1,...
                         SDDSUtil.identifyType(sdds.column.xp.type));
    sdds.column.y.page1=SDDSUtil.castArrayAsDouble(sdds.column.y.page1,...
                        SDDSUtil.identifyType(sdds.column.y.type));
    sdds.column.yp.page1=SDDSUtil.castArrayAsDouble(sdds.column.yp.page1,...
                         SDDSUtil.identifyType(sdds.column.yp.type));
    sdds.column.t.page1=SDDSUtil.castArrayAsDouble(sdds.column.t.page1,...
                        SDDSUtil.identifyType(sdds.column.t.type));
    sdds.column.p.page1=SDDSUtil.castArrayAsDouble(sdds.column.p.page1,...
                        SDDSUtil.identifyType(sdds.column.p.type));
    xpt(:,6)=sdds.column.p.page1;
    xpt(:,1)=sdds.column.x.page1;
    xpt(:,2)=sdds.column.xp.page1;
    xpt(:,3)=sdds.column.y.page1;
    xpt(:,4)=sdds.column.yp.page1;
    xpt(:,5)=sdds.column.t.page1;
    Step=sdds.parameter.Step.data;
    pCentral=sdds.parameter.pCentral.data;
    Charge=sdds.parameter.Charge.data;
    N_part=sdds.parameter.Particles.data;
    if nargout>=5
      idx(N_part,1)=0;
      for n=1:N_part
          idx(n,1)=double(sdds.column.particleID.page1(n));
      end
    end
else
    if nargout>=4, description='nothing'; end
    xpt=0;
    Step=0;
    pCentral=0;
    Charge;
    Q_in_Culoumb=0;
    N_part=0;
    if nargout>=5, idx=0; end
end
end

