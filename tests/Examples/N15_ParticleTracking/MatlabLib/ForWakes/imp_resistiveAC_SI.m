% resistive impedance of round pipe (in SI Units)
% dimensions: f - Hertz
%             % cond - in 1/Second
%             a - pipe radius in m;  
%             L-inductive for dielectric layer
function Z = imp_resistiveAC_SI(f,cond,a,t,L);
PhysConsts;
n=length(f);
f2w=2*pi;
koef=a*0.5*complex(0,1)/(c*Z0);
for i=1:n,
    w=f(i)*f2w;
    kw=cond/(1+complex(0,1)*w*t);
    Zs=sqrt(complex(0,1)*w*mue0/kw)+complex(0,1)*w*L;
    Z(i)=Zs/(f2w*a*(1+w*Zs*koef));
end
