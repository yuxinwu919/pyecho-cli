function P=compressor(P,E0,R56,T566,U5666)
% P=compressor(P,E0,R56,T566,U5666)
d=(P(:,2)-E0)/E0;
P(:,1)=P(:,1)-R56*d;
if T566~=0,
    d2=d.*d;
    P(:,1)=P(:,1)-T566*d2;
end;
if U5666~=0,
    if T566==0,d2=d.*d;end;
    P(:,1)=P(:,1)-U5666*d.*d2;
end;
    